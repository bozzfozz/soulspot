# Hey future me - DAS ist der zentrale Worker-Orchestrator!
#
# PROBLEM (Dec 2025): lifecycle.py war 937 Zeilen lang, davon ~600 Zeilen Worker-Management.
# Jeder Worker hatte eigene Start/Stop-Logik, verstreut auf app.state, inkonsistente Patterns.
# Debugging war ein Albtraum - welcher Worker läuft? Welcher ist crashed?
#
# LÖSUNG: Ein zentraler Orchestrator der:
# - Alle Worker registriert und verwaltet
# - Einheitliche Start/Stop-Sequenzen bietet
# - Health-Status für alle Worker trackt
# - Dependencies zwischen Workern kennt (z.B. TokenRefresh VOR SpotifySync)
# - Graceful Shutdown mit Timeouts koordiniert
# - API für Status-Monitoring bereitstellt (/api/workers/status)
#
# DESIGN:
# - Worker registrieren sich via orchestrator.register(worker, priority)
# - Start: Alle Worker in Priority-Reihenfolge starten (niedrigere Zahl = früher)
# - Stop: Umgekehrte Reihenfolge (höhere Priority zuerst stoppen)
# - Health: Jeder Worker hat .get_status() Methode
#
# OPTIMIERUNGEN (Dec 2025):
# - PARALLEL STARTUP: Worker ohne Dependencies starten gleichzeitig
# - AUTO-RECOVERY: Task-Worker werden bei Crash automatisch neu gestartet
# - restart_worker(): Einzelne Worker können neu gestartet werden
# - CYCLE DETECTION: Zyklische Dependencies werden beim Register erkannt
#
# USAGE:
#   orchestrator = WorkerOrchestrator()
#   orchestrator.register(token_worker, priority=1, name="token_refresh")
#   orchestrator.register(spotify_worker, priority=2, name="spotify_sync")
#   await orchestrator.start_all()
#   ...
#   await orchestrator.stop_all()
"""Centralized Worker Orchestrator for background task management."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker lifecycle states."""

    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@runtime_checkable
class Worker(Protocol):
    """Protocol for workers managed by the orchestrator.

    Hey future me - workers MUST implement these methods to be manageable:
    - start(): Async method to start the worker
    - stop(): Async method to stop the worker gracefully
    - get_status(): Returns dict with worker status info

    Optional:
    - is_running: Property to check if worker is active
    """

    async def start(self) -> None:
        """Start the worker."""
        ...

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Get worker status information."""
        ...


@dataclass
class WorkerInfo:
    """Information about a registered worker."""

    worker: Worker
    name: str
    priority: int
    category: str = "general"
    required: bool = True  # If True, failure stops startup
    depends_on: list[str] = field(default_factory=list)
    state: WorkerState = WorkerState.REGISTERED
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = None  # For task-based workers
    restart_count: int = 0  # Track restarts for auto-recovery


class TaskWorkerWrapper:
    """Wraps an asyncio.Task to implement Worker protocol.

    Hey future me - extracted this to avoid code duplication!
    Used by both register_task_worker() and register_running_task().
    """

    def __init__(self, task: asyncio.Task[None], name: str) -> None:
        self._task = task
        self._name = name
        self._stopped = False

    async def start(self) -> None:
        """No-op - task already started."""
        pass

    async def stop(self) -> None:
        """Cancel and wait for task."""
        self._stopped = True
        if not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.CancelledError, TimeoutError):
                pass

    def get_status(self) -> dict[str, Any]:
        """Get task status."""
        return {
            "name": self._name,
            "running": not self._task.done() and not self._stopped,
            "status": self._compute_status(),
        }

    def _compute_status(self) -> str:
        """Compute status string from task state."""
        if self._stopped:
            return "stopped"
        if self._task.done():
            return "completed" if not self._task.exception() else "failed"
        return "running"


@dataclass
class WorkerOrchestrator:
    """Centralized orchestrator for all background workers.

    Hey future me - this is THE place for worker management!

    Features:
    - Priority-based startup (lower number = starts first)
    - Dependency tracking (worker A needs worker B running first)
    - Graceful shutdown with configurable timeout
    - Health status for all workers
    - Consistent logging and error handling

    Categories:
    - "critical": Must succeed for app to start (token_refresh, job_queue)
    - "sync": Data synchronization workers (spotify_sync, deezer_sync)
    - "download": Download management (download_worker, monitor, dispatcher)
    - "maintenance": Cleanup, duplicate detection
    - "enrichment": Library discovery, image backfill
    """

    shutdown_timeout: float = 10.0  # Seconds to wait for graceful shutdown
    startup_timeout: float = 30.0  # Seconds to wait for worker to start
    auto_recovery_enabled: bool = True  # Enable automatic crash recovery
    auto_recovery_max_restarts: int = 3  # Max restarts before giving up

    # Internal state
    _workers: dict[str, WorkerInfo] = field(default_factory=dict)
    _started: bool = False
    _shutting_down: bool = False
    _monitor_task: asyncio.Task[None] | None = None  # Background health monitor

    def _detect_dependency_cycle(
        self, name: str, visited: set[str] | None = None, path: list[str] | None = None
    ) -> list[str] | None:
        """Detect circular dependencies in worker graph.

        Hey future me - this prevents nasty deadlocks at startup!
        Returns the cycle path if found, None otherwise.

        Args:
            name: Worker name to check
            visited: Set of already visited workers
            path: Current path in DFS traversal

        Returns:
            Cycle path if cycle detected, None otherwise
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if name in path:
            # Found cycle! Return the cycle path
            cycle_start = path.index(name)
            return path[cycle_start:] + [name]

        if name in visited:
            return None  # Already checked, no cycle through this node

        visited.add(name)
        path.append(name)

        info = self._workers.get(name)
        if info:
            for dep in info.depends_on:
                cycle = self._detect_dependency_cycle(dep, visited, path.copy())
                if cycle:
                    return cycle

        return None

    def register(
        self,
        *,  # All arguments must be keyword-only for clarity
        name: str,
        worker: Worker,
        priority: int = 50,
        category: str = "general",
        required: bool = True,
        depends_on: list[str] | None = None,
        task: asyncio.Task[None] | None = None,
    ) -> None:
        """Register a worker with the orchestrator.

        Args:
            name: Unique name for the worker (used for dependencies)
            worker: The worker instance (must implement Worker protocol)
            priority: Start priority (lower = starts first)
            category: Category for grouping (critical, sync, download, etc.)
            required: If True, failure stops startup. If False, continues with warning
            depends_on: List of worker names that must be running first
            task: Optional asyncio.Task if worker runs as task (for proper cancellation)
        """
        if name in self._workers:
            logger.warning(f"Worker '{name}' already registered, updating")

        self._workers[name] = WorkerInfo(
            worker=worker,
            name=name,
            priority=priority,
            category=category,
            required=required,
            depends_on=depends_on or [],
            task=task,
        )

        # Check for dependency cycles after registration
        cycle = self._detect_dependency_cycle(name)
        if cycle:
            del self._workers[name]
            cycle_str = " → ".join(cycle)
            raise ValueError(
                f"Circular dependency detected for worker '{name}': {cycle_str}"
            )

        logger.debug(
            f"Registered worker: {name} (priority={priority}, category={category}, required={required})"
        )

    def register_task_worker(
        self,
        coro: Any,  # Coroutine to run as task
        name: str,
        priority: int = 50,
        category: str = "general",
        required: bool = True,
        depends_on: list[str] | None = None,
    ) -> asyncio.Task[None]:
        """Register a coroutine-based worker that runs as an asyncio task.

        Hey future me - some workers use create_task() instead of start()/stop().
        This method handles that pattern by wrapping the coroutine.

        Args:
            coro: Coroutine to run (NOT the result of create_task!)
            name: Unique worker name
            priority: Start priority
            category: Category for grouping
            required: If True, failure stops startup
            depends_on: List of dependencies

        Returns:
            The created asyncio.Task (for backwards compatibility)
        """
        task = asyncio.create_task(coro)
        wrapper = TaskWorkerWrapper(task, name)

        info = WorkerInfo(
            worker=wrapper,  # type: ignore
            name=name,
            priority=priority,
            category=category,
            required=required,
            depends_on=depends_on or [],
            state=WorkerState.RUNNING,  # Already running
            started_at=datetime.now(UTC),
            task=task,
        )
        self._workers[name] = info

        return task

    def register_running_task(
        self,
        *,
        name: str,
        task: asyncio.Task[None],
        worker: Worker | None = None,
        priority: int = 50,
        category: str = "general",
        required: bool = False,
    ) -> None:
        """Register an already-running task with the orchestrator for tracking.

        Hey future me - use this for workers that are started via create_task()!
        Unlike register() which expects orchestrator to call start(), this method
        registers a task that's ALREADY RUNNING.

        Args:
            name: Unique worker name
            task: Already-running asyncio.Task
            worker: Optional worker instance (for stop() if available)
            priority: Priority (only for sorting in status output)
            category: Category for grouping
            required: If True, health check fails if task dies
        """
        # Use provided worker or create wrapper
        effective_worker: Worker
        if worker is not None:
            effective_worker = worker
        else:
            effective_worker = TaskWorkerWrapper(task, name)  # type: ignore

        info = WorkerInfo(
            worker=effective_worker,
            name=name,
            priority=priority,
            category=category,
            required=required,
            depends_on=[],
            state=WorkerState.RUNNING,  # Already running!
            started_at=datetime.now(UTC),
            task=task,
        )
        self._workers[name] = info

        logger.debug(f"Registered running task: {name} (category={category})")

    async def start_all(self) -> bool:
        """Start all registered workers in priority order with PARALLEL startup.

        OPTIMIZED (Dec 2025): Workers within the same priority group start in parallel!
        This significantly speeds up startup when multiple independent workers exist.

        Returns:
            True if all required workers started successfully
        """
        if self._started:
            logger.warning("Workers already started")
            return True

        logger.info("=" * 60)
        logger.info("🚀 WORKER ORCHESTRATOR - Starting all workers (PARALLEL MODE)")
        logger.info("=" * 60)
        logger.info(f"  📊 Registered workers: {len(self._workers)}")

        # Sort by priority
        sorted_workers = sorted(self._workers.values(), key=lambda w: w.priority)

        # Group by category for logging
        by_category: dict[str, list[WorkerInfo]] = {}
        for w in sorted_workers:
            by_category.setdefault(w.category, []).append(w)

        for cat, workers in by_category.items():
            logger.info(f"  📦 {cat}: {', '.join(w.name for w in workers)}")

        logger.info("-" * 60)

        # Group workers by priority for parallel startup
        priority_groups: dict[int, list[WorkerInfo]] = defaultdict(list)
        for w in sorted_workers:
            priority_groups[w.priority].append(w)

        success = True
        started_count = 0

        # Process each priority group in order
        for priority in sorted(priority_groups.keys()):
            group = priority_groups[priority]

            # Collect workers ready to start (deps met, not already running)
            ready_workers: list[WorkerInfo] = []

            for info in group:
                # Skip already running (task workers)
                if info.state == WorkerState.RUNNING:
                    logger.info(f"  ⏭️  {info.name}: Already running (task)")
                    started_count += 1
                    continue

                # Check dependencies
                unmet_deps = [
                    dep
                    for dep in info.depends_on
                    if dep not in self._workers
                    or self._workers[dep].state != WorkerState.RUNNING
                ]
                if unmet_deps:
                    if info.required:
                        logger.error(
                            f"  ❌ {info.name}: Unmet dependencies: {unmet_deps}"
                        )
                        info.state = WorkerState.FAILED
                        info.error = f"Unmet dependencies: {unmet_deps}"
                        success = False
                        break
                    else:
                        logger.warning(
                            f"  ⚠️  {info.name}: Skipping due to unmet dependencies: {unmet_deps}"
                        )
                        continue

                ready_workers.append(info)

            if not success:
                break

            if not ready_workers:
                continue

            # Start all ready workers in this priority group in PARALLEL!
            if len(ready_workers) > 1:
                logger.info(
                    f"  🔀 Starting {len(ready_workers)} workers in parallel (priority={priority})"
                )

            async def start_single_worker(
                info: WorkerInfo,
            ) -> tuple[WorkerInfo, Exception | None]:
                """Start a single worker and return result (with timeout)."""
                info.state = WorkerState.STARTING
                try:
                    # Apply startup timeout to prevent hanging workers
                    await asyncio.wait_for(
                        info.worker.start(), timeout=self.startup_timeout
                    )
                    info.state = WorkerState.RUNNING
                    info.started_at = datetime.now(UTC)
                    return (info, None)
                except TimeoutError:
                    info.state = WorkerState.FAILED
                    info.error = f"Startup timeout ({self.startup_timeout}s)"
                    return (info, TimeoutError(f"Worker {info.name} startup timeout"))
                except Exception as e:
                    info.state = WorkerState.FAILED
                    info.error = str(e)
                    return (info, e)

            # Run all starts in parallel
            results = await asyncio.gather(
                *[start_single_worker(w) for w in ready_workers],
                return_exceptions=False,
            )

            # Process results
            for info, error in results:
                if error is None:
                    started_count += 1
                    logger.info(f"  ✅ {info.name}: Started")
                else:
                    if info.required:
                        logger.error(f"  ❌ {info.name}: Failed to start - {error}")
                        success = False
                    else:
                        logger.warning(
                            f"  ⚠️  {info.name}: Failed to start (non-required) - {error}"
                        )

            if not success:
                break

        self._started = True

        # Start auto-recovery monitor if enabled
        if self.auto_recovery_enabled and success:
            self._monitor_task = asyncio.create_task(self._monitor_worker_health())
            logger.info("  🏥 Auto-recovery monitor started")

        logger.info("=" * 60)
        if success:
            logger.info(
                f"✅ WORKER ORCHESTRATOR - {started_count} workers started successfully"
            )
        else:
            logger.error(
                f"❌ WORKER ORCHESTRATOR - Startup failed ({started_count} started)"
            )
        logger.info("=" * 60)

        return success

    async def stop_all(self) -> None:
        """Stop all workers in reverse priority order with PARALLEL shutdown.

        OPTIMIZED (Dec 2025): Workers within the same priority group stop in parallel!
        This significantly speeds up shutdown - from O(n×timeout) to O(groups×timeout).

        Hey future me - handles BOTH async and sync stop() methods!
        Some workers (QueueDispatcherWorker, RetrySchedulerWorker) have sync stop().
        We check if stop() is a coroutine before awaiting it.
        """
        if self._shutting_down:
            logger.warning("Already shutting down workers")
            return

        self._shutting_down = True

        # Stop auto-recovery monitor first
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("  🏥 Auto-recovery monitor stopped")

        logger.info("=" * 60)
        logger.info("🛑 WORKER ORCHESTRATOR - Stopping all workers (PARALLEL MODE)")
        logger.info("=" * 60)

        # Sort by priority (reverse - higher priority stops first)
        sorted_workers = sorted(
            self._workers.values(), key=lambda w: w.priority, reverse=True
        )

        # Group by priority for parallel shutdown
        priority_groups: dict[int, list[WorkerInfo]] = defaultdict(list)
        for w in sorted_workers:
            if w.state in (WorkerState.RUNNING, WorkerState.STARTING):
                priority_groups[w.priority].append(w)

        stopped_count = 0

        async def stop_single_worker(info: WorkerInfo) -> tuple[WorkerInfo, bool]:
            """Stop a single worker and return success status."""
            info.state = WorkerState.STOPPING
            success = False

            try:
                # Handle both async and sync stop() methods
                stop_result = info.worker.stop()
                if asyncio.iscoroutine(stop_result):
                    await asyncio.wait_for(stop_result, timeout=self.shutdown_timeout)

                # If worker has an associated task, wait for it to complete
                if info.task is not None and not info.task.done():
                    try:
                        await asyncio.wait_for(info.task, timeout=self.shutdown_timeout)
                    except TimeoutError:
                        logger.warning(f"  ⏱️  {info.name}: Task timeout, cancelling...")
                        info.task.cancel()
                        try:
                            await info.task
                        except asyncio.CancelledError:
                            pass

                info.state = WorkerState.STOPPED
                info.stopped_at = datetime.now(UTC)
                success = True

            except TimeoutError:
                logger.warning(f"  ⏱️  {info.name}: Timeout during shutdown, forcing...")
                if info.task:
                    info.task.cancel()
                info.state = WorkerState.STOPPED
                info.stopped_at = datetime.now(UTC)
                success = True  # Forced stop counts as success

            except Exception as e:
                logger.error(f"  ❌ {info.name}: Error during shutdown - {e}")
                info.state = WorkerState.FAILED
                info.error = str(e)

            return (info, success)

        # Process each priority group in PARALLEL
        for priority in sorted(priority_groups.keys(), reverse=True):
            group = priority_groups[priority]

            if not group:
                continue

            if len(group) > 1:
                logger.info(
                    f"  🔀 Stopping {len(group)} workers in parallel (priority={priority})"
                )

            # Stop all workers in this priority group in parallel!
            results = await asyncio.gather(
                *[stop_single_worker(w) for w in group], return_exceptions=False
            )

            # Process results
            for info, success in results:
                if success:
                    stopped_count += 1
                    logger.info(f"  ✅ {info.name}: Stopped")
                else:
                    logger.error(f"  ❌ {info.name}: Failed to stop")

        self._started = False
        self._shutting_down = False

        logger.info("=" * 60)
        logger.info(f"🛑 WORKER ORCHESTRATOR - {stopped_count} workers stopped")
        logger.info("=" * 60)

    async def restart_worker(self, name: str, reason: str = "manual") -> bool:
        """Restart a specific worker gracefully.

        Hey future me - use this for manual restarts or auto-recovery!

        Args:
            name: Worker name to restart
            reason: Reason for restart (for logging)

        Returns:
            True if restart succeeded
        """
        info = self._workers.get(name)
        if not info:
            logger.error(f"♻️ Cannot restart unknown worker: {name}")
            return False

        logger.info(f"♻️ Restarting {name}: {reason}")

        # Stop worker first
        info.state = WorkerState.STOPPING

        try:
            stop_result = info.worker.stop()
            if asyncio.iscoroutine(stop_result):
                await asyncio.wait_for(stop_result, timeout=5.0)
        except Exception as e:
            logger.warning(f"  ⚠️ {name}: Error during stop (continuing restart): {e}")

        # Wait brief moment for cleanup
        await asyncio.sleep(0.5)

        # Start worker
        info.state = WorkerState.STARTING
        try:
            # Apply startup timeout
            await asyncio.wait_for(info.worker.start(), timeout=self.startup_timeout)
            info.state = WorkerState.RUNNING
            info.started_at = datetime.now(UTC)
            info.restart_count += 1
            info.error = None
            logger.info(
                f"  ✅ {name}: Restarted successfully (restart #{info.restart_count})"
            )
            return True

        except TimeoutError:
            info.state = WorkerState.FAILED
            info.error = f"Restart startup timeout ({self.startup_timeout}s)"
            logger.error(f"  ❌ {name}: Restart startup timeout")
            return False

        except Exception as e:
            info.state = WorkerState.FAILED
            info.error = f"Restart failed: {e}"
            logger.error(f"  ❌ {name}: Restart failed - {e}")
            return False

    async def _monitor_worker_health(self) -> None:
        """Background task that monitors task-workers and restarts if crashed.

        Hey future me - this is the AUTO-RECOVERY system!
        It watches all task-based workers and restarts them if they crash.

        - Runs every 5 seconds
        - Only restarts up to auto_recovery_max_restarts times
        - Only restarts non-required workers (required ones would have killed startup)
        """
        logger.debug("Auto-recovery monitor started")

        while not self._shutting_down:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds

                if self._shutting_down:
                    break

                for name, info in list(self._workers.items()):
                    # Only monitor task-based workers
                    if info.task is None:
                        continue

                    # Check if task crashed
                    if info.task.done() and info.state == WorkerState.RUNNING:
                        exc = info.task.exception()
                        if exc:
                            logger.warning(f"⚠️ Worker {name} crashed: {exc}")
                            info.state = WorkerState.FAILED
                            info.error = str(exc)

                            # Try auto-recovery if within limits
                            if info.restart_count < self.auto_recovery_max_restarts:
                                logger.info(f"  🔄 Attempting auto-recovery for {name}")
                                await self.restart_worker(
                                    name,
                                    f"crash_recovery (attempt {info.restart_count + 1})",
                                )
                            else:
                                logger.error(
                                    f"  ❌ {name}: Max restarts ({self.auto_recovery_max_restarts}) reached, giving up"
                                )
                        else:
                            # Task completed without error (unusual for workers)
                            logger.info(f"  ℹ️ {name}: Task completed naturally")
                            info.state = WorkerState.STOPPED

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-recovery monitor error: {e}")

        logger.debug("Auto-recovery monitor stopped")

    def get_status(self) -> dict[str, Any]:
        """Get status of all workers for API/UI.

        Returns:
            Dict with overall status and per-worker details
        """
        workers_dict: dict[str, dict[str, Any]] = {}

        for name, info in self._workers.items():
            # Get worker's own status
            try:
                worker_status = info.worker.get_status()
            except Exception:
                worker_status = {}

            workers_dict[name] = {
                "name": name,
                "category": info.category,
                "priority": info.priority,
                "state": info.state.value,
                "required": info.required,
                "started_at": info.started_at.isoformat() if info.started_at else None,
                "stopped_at": info.stopped_at.isoformat() if info.stopped_at else None,
                "error": info.error,
                "depends_on": info.depends_on,
                "restart_count": info.restart_count,
                **worker_status,  # Merge worker's own status
            }

        # Group by state
        by_state = {state.value: 0 for state in WorkerState}
        for w in workers_dict.values():
            by_state[w["state"]] += 1

        return {
            "total_workers": len(self._workers),
            "started": self._started,
            "shutting_down": self._shutting_down,
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "auto_recovery_monitor_running": self._monitor_task is not None
            and not self._monitor_task.done(),
            "by_state": by_state,
            "workers": workers_dict,  # Dict keyed by worker name
        }

    def get_worker(self, name: str) -> Worker | None:
        """Get a specific worker by name.

        Args:
            name: Worker name

        Returns:
            Worker instance or None if not found
        """
        info = self._workers.get(name)
        return info.worker if info else None

    def is_healthy(self) -> bool:
        """Check if all required workers are running.

        Returns:
            True if all required workers are in RUNNING state
        """
        for info in self._workers.values():
            if info.required and info.state != WorkerState.RUNNING:
                return False
        return True

    def mark_all_running(self) -> None:
        """Mark all registered workers as RUNNING state.

        Hey future me - this is for TRACKING MODE only!
        When lifecycle.py starts workers itself (not via orchestrator.start_all()),
        we need to manually mark them as running for status tracking to work.

        Usage:
            # After all workers have been started by lifecycle.py
            orchestrator.mark_all_running()
        """
        now = datetime.now(UTC)
        for name, info in self._workers.items():
            if info.state == WorkerState.REGISTERED:
                info.state = WorkerState.RUNNING
                info.started_at = now
                logger.debug(f"Marked worker '{name}' as running (tracking mode)")


# Singleton orchestrator instance for the application
_orchestrator: WorkerOrchestrator | None = None


def get_orchestrator() -> WorkerOrchestrator:
    """Get the global orchestrator instance.

    Creates one if not exists. Use this in lifecycle.py and dependencies.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkerOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the global orchestrator (for testing)."""
    global _orchestrator
    _orchestrator = None

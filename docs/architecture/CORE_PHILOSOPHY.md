# SoulSpot Core Philosophy

> **"SoulSpot is Autonomous"**

## 1. The Autonomy Principle
SoulSpot is a self-contained, autonomous system. It manages, processes, and organizes everything internally. It does not rely on external services for logic or state management.

- **SoulSpot is the Brain**: It makes all decisions (what to download, when to pause, how to tag).
- **External Services are Tools**: Other services are merely "dumb" tools used by SoulSpot to achieve its goals.

## 2. Plugin Architecture (Data Sources)
Services like **Spotify**, **Deezer**, and **Tidal** are treated strictly as **Data Sources (Plugins)**.

- **Role**: They provide metadata, playlists, and discovery data.
- **Constraint**: SoulSpot fetches data from them, but never relies on them for storage or business logic.
- **Abstraction**: SoulSpot converts external data into its own internal Domain Entities immediately.

## 3. Download Management (The "Two Queue" System)
SoulSpot uses external downloaders (like **Soulseek/slskd**) but maintains strict control over them.

### The Control Loop
1.  **Internal Queue (SoulSpot)**: All download requests start here. SoulSpot prioritizes and manages this queue.
2.  **Throttled Feeding**: SoulSpot feeds downloads to the external service (slskd) incrementally (e.g., 5 at a time).
3.  **External Queue (Soulseek)**: The external service handles the actual file transfer.
4.  **API Control**: SoulSpot constantly monitors and controls the external service via API (pausing, removing, checking status).

**Why?**
- Prevents overwhelming the external service.
- Keeps the "Source of Truth" inside SoulSpot.
- Allows swapping download providers (e.g., switching from Soulseek to Torrent) without changing the core logic.

## 4. Summary
**We are completely autonomous.** Other services exist only to serve data to SoulSpot.

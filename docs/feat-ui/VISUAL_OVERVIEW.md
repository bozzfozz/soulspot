# ⚠️ DEPRECATED - SoulSpot UI Redesign - Visual Overview

## Document Information
- **Version**: 1.0 (DEPRECATED)
- **Last Updated**: 2025-11-26
- **Status**: ❌ DEPRECATED
- **Replaced By:** [feat-ui-pro.md](./feat-ui-pro.md) + actual implementations in `src/soulspot/static/css/` and `src/soulspot/templates/`
- **Date Deprecated:** 9. Dezember 2025
- **Reason:** Visual specs outdated. Actual CSS exists in `static/css/variables.css` (violet #8b5cf6, not red #fe4155). Templates exist in `templates/` with HTMX integration.

**DO NOT USE THIS FILE. See `src/soulspot/static/css/variables.css` for current visual design.**

---

<details>
<summary>Original Content (Archived)</summary>

## Project Timeline

```mermaid
gantt
    title SoulSpot UI Redesign Timeline
    dateFormat YYYY-MM-DD
    section Phase 1
    Foundation & Architecture           :p1, 2025-11-27, 14d
    section Phase 2
    Core Navigation & Layout            :p2, after p1, 14d
    section Phase 3
    Library Management System           :p3, after p2, 21d
    section Phase 4
    Activity & Download Management      :p4, after p3, 14d
    section Phase 5
    Search & Discovery                  :p5, after p4, 14d
    section Phase 6
    Settings & Configuration            :p6, after p5, 7d
    section Phase 7
    Dashboard Enhancement               :p7, after p6, 7d
    section Phase 8
    Polish & Optimization               :p8, after p7, 14d
```

---

## Component Hierarchy

```mermaid
graph TB
    Base[base.html - Base Layout]
    
    Base --> Layout[Layout Components]
    Base --> Navigation[Navigation Components]
    Base --> DataDisplay[Data Display Components]
    Base --> Input[Input Components]
    Base --> Feedback[Feedback Components]
    Base --> Specialized[Specialized Components]
    
    Layout --> Sidebar[Sidebar]
    Layout --> TopBar[TopBar]
    Layout --> PageHeader[PageHeader]
    Layout --> Container[Container]
    
    Navigation --> Breadcrumbs[Breadcrumbs]
    Navigation --> Tabs[Tabs]
    Navigation --> Pagination[Pagination]
    
    DataDisplay --> Card[Card]
    DataDisplay --> Table[Table]
    DataDisplay --> Grid[Grid]
    DataDisplay --> Badge[Badge]
    
    Input --> Button[Button]
    Input --> InputField[Input]
    Input --> Select[Select]
    Input --> FilterPanel[FilterPanel]
    Input --> SearchBar[SearchBar]
    
    Feedback --> Alert[Alert]
    Feedback --> Toast[Toast]
    Feedback --> Modal[Modal]
    Feedback --> Loading[Loading]
    Feedback --> ProgressBar[ProgressBar]
    
    Specialized --> LibraryView[LibraryView]
    Specialized --> QueueManager[QueueManager]
    Specialized --> ActivityFeed[ActivityFeed]
    
    style Base fill:#fe4155,stroke:#982633,color:#fff
    style Layout fill:#533c5b,stroke:#332538,color:#fff
    style Navigation fill:#533c5b,stroke:#332538,color:#fff
    style DataDisplay fill:#533c5b,stroke:#332538,color:#fff
    style Input fill:#533c5b,stroke:#332538,color:#fff
    style Feedback fill:#533c5b,stroke:#332538,color:#fff
    style Specialized fill:#533c5b,stroke:#332538,color:#fff
```

---

## Application Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        Templates[Jinja2 Templates]
        Components[Reusable Components]
        CSS[CSS Modules]
        JS[JavaScript Modules]
    end
    
    subgraph "Integration Layer"
        HTMX[HTMX Dynamic Loading]
        API[REST API Calls]
        SSE[Server-Sent Events]
    end
    
    subgraph "Backend Layer"
        FastAPI[FastAPI Server]
        Database[(PostgreSQL)]
        Spotify[Spotify API]
        Soulseek[Soulseek Client]
    end
    
    Templates --> HTMX
    Components --> Templates
    CSS --> Templates
    JS --> API
    HTMX --> FastAPI
    API --> FastAPI
    SSE --> FastAPI
    FastAPI --> Database
    FastAPI --> Spotify
    FastAPI --> Soulseek
    
    style Templates fill:#3b82f6,stroke:#2563eb,color:#fff
    style FastAPI fill:#10b981,stroke:#059669,color:#fff
    style Database fill:#f59e0b,stroke:#d97706,color:#fff
```

---

## Page Structure

```mermaid
graph LR
    subgraph "Main Layout"
        Sidebar[Sidebar Navigation]
        TopBar[Top Bar]
        Content[Main Content Area]
    end
    
    Sidebar --> Dashboard[Dashboard]
    Sidebar --> Library[Library]
    Sidebar --> Playlists[Playlists]
    Sidebar --> Downloads[Downloads]
    Sidebar --> Search[Search]
    Sidebar --> Settings[Settings]
    
    Library --> Artists[Artists View]
    Library --> Albums[Albums View]
    Library --> Tracks[Tracks View]
    
    Artists --> ArtistDetail[Artist Detail]
    Albums --> AlbumDetail[Album Detail]
    
    Playlists --> PlaylistList[Playlist List]
    PlaylistList --> PlaylistDetail[Playlist Detail]
    
    Downloads --> Queue[Download Queue]
    Downloads --> History[Download History]
    
    style Sidebar fill:#1f2937,stroke:#4b5563,color:#f9fafb
    style TopBar fill:#1f2937,stroke:#4b5563,color:#f9fafb
    style Content fill:#111827,stroke:#374151,color:#f9fafb
```

---

## Library View States

```mermaid
stateDiagram-v2
    [*] --> Loading
    Loading --> GridView: Load Complete
    Loading --> ListView: Load Complete
    Loading --> TableView: Load Complete
    
    GridView --> ListView: Toggle View
    GridView --> TableView: Toggle View
    ListView --> GridView: Toggle View
    ListView --> TableView: Toggle View
    TableView --> GridView: Toggle View
    TableView --> ListView: Toggle View
    
    GridView --> Filtering: Apply Filter
    ListView --> Filtering: Apply Filter
    TableView --> Filtering: Apply Filter
    
    Filtering --> GridView: Filter Applied
    Filtering --> ListView: Filter Applied
    Filtering --> TableView: Filter Applied
    
    GridView --> Sorting: Apply Sort
    ListView --> Sorting: Apply Sort
    TableView --> Sorting: Apply Sort
    
    Sorting --> GridView: Sort Applied
    Sorting --> ListView: Sort Applied
    Sorting --> TableView: Sort Applied
```

---

## Download Queue Flow

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant API
    participant Queue
    participant Soulseek
    
    User->>UI: Add tracks to queue
    UI->>API: POST /api/downloads/queue
    API->>Queue: Add to queue
    Queue-->>API: Queue updated
    API-->>UI: Success response
    UI-->>User: Show confirmation
    
    Queue->>Soulseek: Start download
    Soulseek-->>Queue: Progress updates
    Queue->>API: Emit SSE events
    API->>UI: Real-time progress
    UI->>User: Update progress bar
    
    Soulseek-->>Queue: Download complete
    Queue->>API: Emit completion event
    API->>UI: Update status
    UI->>User: Show completion
```

---

## Component Data Flow

```mermaid
graph LR
    subgraph "User Interaction"
        User[User Action]
    end
    
    subgraph "UI Layer"
        Component[Component]
        State[Local State]
    end
    
    subgraph "API Layer"
        HTMX[HTMX Request]
        Fetch[Fetch API]
        SSE[SSE Stream]
    end
    
    subgraph "Backend"
        Endpoint[API Endpoint]
        DB[(Database)]
    end
    
    User --> Component
    Component --> State
    Component --> HTMX
    Component --> Fetch
    Component --> SSE
    
    HTMX --> Endpoint
    Fetch --> Endpoint
    SSE --> Endpoint
    
    Endpoint --> DB
    DB --> Endpoint
    
    Endpoint --> HTMX
    Endpoint --> Fetch
    Endpoint --> SSE
    
    HTMX --> Component
    Fetch --> Component
    SSE --> Component
    
    Component --> User
    
    style User fill:#fe4155,stroke:#982633,color:#fff
    style Component fill:#3b82f6,stroke:#2563eb,color:#fff
    style Endpoint fill:#10b981,stroke:#059669,color:#fff
    style DB fill:#f59e0b,stroke:#d97706,color:#fff
```

---

## Design System Hierarchy

```mermaid
graph TB
    DesignSystem[Design System]
    
    DesignSystem --> Colors[Colors]
    DesignSystem --> Typography[Typography]
    DesignSystem --> Spacing[Spacing]
    DesignSystem --> Components[Components]
    
    Colors --> Brand[Brand Colors]
    Colors --> Semantic[Semantic Colors]
    Colors --> Neutral[Neutral Colors]
    
    Brand --> Primary[Primary: #fe4155]
    Brand --> Secondary[Secondary: #533c5b]
    
    Semantic --> Success[Success: #10b981]
    Semantic --> Warning[Warning: #f59e0b]
    Semantic --> Danger[Danger: #ef4444]
    Semantic --> Info[Info: #3b82f6]
    
    Neutral --> Background[Background: #111827]
    Neutral --> Surface[Surface: #1f2937]
    Neutral --> Text[Text: #f9fafb]
    
    Typography --> FontFamily[Font: Inter]
    Typography --> FontSizes[Sizes: xs-5xl]
    Typography --> FontWeights[Weights: 400-700]
    
    Spacing --> BaseUnit[Base: 4px]
    Spacing --> Scale[Scale: xs-4xl]
    
    Components --> Layout[Layout]
    Components --> Navigation[Navigation]
    Components --> DataDisplay[Data Display]
    Components --> Input[Input]
    Components --> Feedback[Feedback]
    
    style DesignSystem fill:#fe4155,stroke:#982633,color:#fff
    style Colors fill:#533c5b,stroke:#332538,color:#fff
    style Typography fill:#533c5b,stroke:#332538,color:#fff
    style Spacing fill:#533c5b,stroke:#332538,color:#fff
    style Components fill:#533c5b,stroke:#332538,color:#fff
```

---

## Development Workflow

```mermaid
graph LR
    Start([Start]) --> Plan[Plan Feature]
    Plan --> Design[Design Component]
    Design --> Implement[Implement]
    
    Implement --> Template[Create Template]
    Implement --> Styles[Add Styles]
    Implement --> Script[Add JavaScript]
    
    Template --> Test[Test]
    Styles --> Test
    Script --> Test
    
    Test --> Functional{Functional?}
    Functional -->|No| Debug[Debug]
    Debug --> Implement
    
    Functional -->|Yes| Accessible{Accessible?}
    Accessible -->|No| FixA11y[Fix Accessibility]
    FixA11y --> Test
    
    Accessible -->|Yes| Responsive{Responsive?}
    Responsive -->|No| FixResponsive[Fix Responsive]
    FixResponsive --> Test
    
    Responsive -->|Yes| Review[Code Review]
    Review --> Approved{Approved?}
    Approved -->|No| Revise[Revise]
    Revise --> Implement
    
    Approved -->|Yes| Merge[Merge to Main]
    Merge --> End([End])
    
    style Start fill:#10b981,stroke:#059669,color:#fff
    style End fill:#10b981,stroke:#059669,color:#fff
    style Test fill:#3b82f6,stroke:#2563eb,color:#fff
    style Merge fill:#10b981,stroke:#059669,color:#fff
```

---

## File Structure

```
docs/feat-ui/
├── README.md                    # Overview and index
├── ROADMAP.md                   # Complete project roadmap
├── TECHNICAL_SPEC.md            # Technical specification
├── DESIGN_SYSTEM.md             # Design system documentation
├── COMPONENT_LIBRARY.md         # Component library reference
├── IMPLEMENTATION_GUIDE.md      # Implementation guide
└── VISUAL_OVERVIEW.md           # This file

src/soulspot/
├── templates/
│   ├── base.html
│   ├── components/
│   │   ├── layout/
│   │   ├── navigation/
│   │   ├── data-display/
│   │   ├── input/
│   │   ├── feedback/
│   │   └── specialized/
│   ├── pages/
│   │   ├── dashboard.html
│   │   ├── library/
│   │   ├── playlists/
│   │   ├── downloads/
│   │   ├── search.html
│   │   └── settings.html
│   └── includes/
├── static/
│   ├── css/
│   │   ├── base/
│   │   ├── components/
│   │   ├── utilities/
│   │   └── main.css
│   ├── js/
│   │   ├── core/
│   │   ├── components/
│   │   └── utils/
│   └── assets/
└── api/
    └── routers/
        └── ui.py
```

---

## Technology Stack Overview

```mermaid
graph TB
    subgraph "Frontend"
        HTML[HTML/Jinja2]
        CSS[Tailwind CSS + Custom CSS]
        JS[Vanilla JavaScript ES6+]
        HTMX[HTMX 1.9+]
        Icons[Font Awesome 6]
        Fonts[Inter Font]
    end
    
    subgraph "Backend"
        FastAPI[FastAPI]
        Jinja[Jinja2 Templates]
        DB[(PostgreSQL)]
        SpotifyAPI[Spotify API]
        SoulseekClient[Soulseek Client]
    end
    
    subgraph "Build Tools"
        TailwindCLI[Tailwind CLI]
        NPM[npm]
        Poetry[Poetry]
    end
    
    HTML --> FastAPI
    CSS --> HTML
    JS --> HTML
    HTMX --> FastAPI
    Icons --> HTML
    Fonts --> HTML
    
    FastAPI --> Jinja
    FastAPI --> DB
    FastAPI --> SpotifyAPI
    FastAPI --> SoulseekClient
    
    TailwindCLI --> CSS
    NPM --> TailwindCLI
    Poetry --> FastAPI
    
    style HTML fill:#3b82f6,stroke:#2563eb,color:#fff
    style FastAPI fill:#10b981,stroke:#059669,color:#fff
    style DB fill:#f59e0b,stroke:#d97706,color:#fff
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-26  
**Status**: Draft

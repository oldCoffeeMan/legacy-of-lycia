# Legacy of Lycia - Game UI Implementation

## Overview

This document describes the initial MVP implementation of the Legacy of Lycia game UI using server-rendered templates with modern frontend libraries.

## Technology Stack

### Backend
- **FastAPI**: Web framework with Jinja2 templating support
- **Jinja2**: Python templating engine for server-side rendering

### Frontend Libraries (CDN-based)
- **Leaflet.js 1.9.4**: Open-source map rendering library
- **OpenStreetMap**: Free, open-source map tiles
- **HTMX 1.9.10**: Server-driven interactivity without complex JavaScript
- **Alpine.js 3.13.3**: Lightweight reactive framework for UI state management

## Design Decisions

### 1. Server-Side Rendering with Jinja2
**Why?** Simple deployment, no build process, fast initial prototype.

**Migration Path**: Templates consume the same `/api/*` endpoints that a React/Vue SPA would use. When migrating, simply replace templates with a frontend framework while keeping the FastAPI backend unchanged.

### 2. OpenStreetMap + Leaflet
**Why?**
- Both are fully open-source (important for open-source game)
- Leaflet is lightweight (~40KB) and battle-tested
- OpenStreetMap provides free, community-driven map data
- Alternative (MapLibre GL JS) is more modern but heavier

**Map Configuration**:
- Center: 36.2°N, 29.6°E (ancient Lycia region in southwest Anatolia)
- Zoom levels: 7-19 (allows detailed city view while showing regional context)

### 3. HTMX for Interactivity
**Why?** Enables dynamic updates (future: turn progression, city updates) without full page reloads, while keeping logic on the server.

**Future Use Cases**:
- Real-time game state updates
- Form submissions without page refresh
- Partial page updates

### 4. Alpine.js for Client-State
**Why?** Manages ephemeral UI state (hover effects, selected cities, popups) without heavy framework overhead.

**Current Usage**:
- City info panel visibility
- Selected city state
- Map initialization and marker management

### 5. Component-Based CSS
**Why?** Modular styles that are easy to migrate to CSS Modules, Tailwind, or styled-components later.

**Color Scheme**:
- Dark theme (nautical/ancient aesthetic)
- City colors based on game state:
  - Green: High prosperity, low unrest
  - Blue: Moderate prosperity
  - Orange: Struggling cities
  - Red: Low prosperity or high unrest

## File Structure

```
backend/src/lycia/
├── templates/
│   ├── base.html          # Base template with common layout
│   └── game.html          # Main game map view
├── static/
│   ├── css/
│   │   └── main.css       # Game styling
│   └── js/                # (Future: custom JavaScript)
├── app.py                 # FastAPI routes and config
├── models.py              # SQLAlchemy models
└── db.py                  # Database configuration
```

## API Endpoints

### Game UI
- `GET /` - Renders the main game UI (HTML template)

### Data API
- `GET /api/world/snapshot` - Returns current world state and all cities
  ```json
  {
    "tick": 0,
    "cities": [
      {
        "id": 1,
        "name": "Patara",
        "region": "Western Coast",
        "prosperity": 50,
        "unrest": 10,
        "lat": 36.27,
        "lon": 29.32
      },
      ...
    ]
  }
  ```

## Game Features

### Current Implementation
1. **Interactive Map**: OpenStreetMap-based map centered on ancient Lycia
2. **City Markers**: 10 Lycian cities rendered as colored circle markers
3. **City Information**: Hover/click to see city stats (name, region, prosperity, unrest)
4. **Visual Indicators**: City marker colors reflect prosperity and unrest levels
5. **City Labels**: Permanent labels showing city names
6. **Info Panel**: Floating panel showing detailed stats for selected city

### The 10 Cities of Lycia
1. Patara (Western Coast) - 36.27°N, 29.32°E
2. Xanthos (Central Valley) - 36.35°N, 29.32°E
3. Myra (Eastern Foothills) - 36.23°N, 29.98°E
4. Tlos (Northern Highlands) - 36.43°N, 29.35°E
5. Pinara (Central Valley) - 36.56°N, 29.35°E
6. Phaselis (Northern Coast) - 36.52°N, 30.55°E
7. Arycanda (Highlands) - 36.44°N, 30.06°E
8. Olympos (Western Coast) - 36.24°N, 30.47°E
9. Limyra (Eastern Foothills) - 36.37°N, 30.13°E
10. Letoon (Central Valley) - 36.34°N, 29.28°E

## Running the Application

### Prerequisites
- Docker (for PostgreSQL database)
- Python 3.13+
- Virtual environment activated

### Start the Server
```bash
cd backend
PYTHONIOENCODING=utf-8 uvicorn src.lycia.app:app --reload --port 8000
```

### Access the Game
Open browser to: http://127.0.0.1:8000

## Future Enhancements

### Short-term (MVP extensions)
- [ ] Turn progression button (increment tick)
- [ ] City detail view (click to see full stats)
- [ ] Basic animations (prosperity changes, events)
- [ ] Responsive mobile layout

### Medium-term
- [ ] HTMX-powered turn updates (no page refresh)
- [ ] Event system (display historical events on map)
- [ ] Player actions (manage cities, trade routes)
- [ ] Save/load game state

### Long-term (Possible React Migration)
- [ ] Replace templates with React/Next.js SPA
- [ ] Keep FastAPI backend with same API endpoints
- [ ] Add WebSocket support for real-time multiplayer
- [ ] Advanced 3D map visualizations
- [ ] Mobile app using React Native

## Migration Strategy to React

When ready to migrate to React:

1. **Keep FastAPI backend unchanged** - all data APIs already exist
2. **Create React app** consuming `/api/*` endpoints
3. **Reuse component structure**:
   - `App.tsx` → base layout (header, footer)
   - `GameMap.tsx` → map view (use react-leaflet)
   - `CityInfoPanel.tsx` → city detail panel
4. **Port CSS to CSS Modules or Tailwind**
5. **Add React Router** for navigation
6. **Optional**: Add state management (Redux, Zustand)
7. **Optional**: Add build optimization (Vite, Next.js)

## Responsive Design

The UI adapts to different screen sizes:
- **Desktop**: Full map with floating info panel
- **Mobile**: Stacked layout, collapsible info panel

## Accessibility

- Semantic HTML structure
- Keyboard navigation support (Leaflet built-in)
- ARIA labels for interactive elements
- High contrast color scheme

## Performance Considerations

- **CDN Libraries**: Fast initial load from global CDNs
- **Lazy Loading**: Map tiles load on demand
- **Minimal JS**: Alpine.js is only ~15KB gzipped
- **Server-side Rendering**: Fast time-to-interactive

## License

This game is open-source. All libraries used are also open-source:
- Leaflet: BSD 2-Clause License
- OpenStreetMap: ODbL
- HTMX: BSD 2-Clause License
- Alpine.js: MIT License

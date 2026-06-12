# Physics/Tree Layout Toggle Feature

## Overview
Toggle between two graph visualization modes:
- **PHYSICS** (default): D3 force simulation creates natural cluster distribution
- **TREE**: Hierarchical tree layout (BFS-based radial positioning)

## Implementation Details

### 1. Global State Variables (line 3689-3690)
```javascript
let usePhysicsLayout = true;         // Current mode flag
let treeLayoutPositions = {};        // Cache tree coordinates
```

### 2. UI Components

#### Toggle Button (line 1244-1246)
```html
<div style="border-top: 1px solid var(--border); margin-top: 10px; padding-top: 10px;">
  <button id="physics-toggle" class="physics-btn active" title="Toggle...">PHYSICS</button>
</div>
```
- Located in `#stats-panel` bottom section
- Shows current mode: "PHYSICS" or "TREE"
- Active class changes color

#### CSS Styles (line 619-643)
```css
.physics-btn { /* base styling */ }
.physics-btn:hover { /* highlight */ }
.physics-btn.active { /* active state - orange */ }
```

### 3. Core Functions (line 5348-5470)

#### `calculateTreeLayout(nodes, links)`
- **Purpose**: Compute hierarchical positions using BFS
- **Algorithm**:
  1. Find root node (highest connectivity)
  2. BFS traversal assigns depth level to each node
  3. Position nodes in concentric circles by level
  4. Z-axis scales with depth
- **Returns**: `{ nodeId: {x, y, z} }` position map

#### `applyTreeLayout()`
- **Purpose**: Set graph to tree mode
- **Steps**:
  1. Calculate tree positions (or use cached)
  2. Apply x,y,z coordinates to all nodes
  3. Zero out velocities (vx, vy, vz)
  4. Remove all D3 forces
  5. Trigger frame refresh
- **Result**: Static, hierarchical layout

#### `applyPhysicsForces()`
- **Purpose**: Set graph back to physics mode
- **Steps**:
  1. Re-enable D3 force parameters:
     - `charge`: -5 (external) or -25 (internal)
     - `link`: distance 50/100, strength varies
     - `position` force: 0.18 strength (internal only)
  2. Trigger frame refresh
- **Result**: Dynamic force simulation

#### `togglePhysicsLayout()`
- **Purpose**: Switch between modes
- **Steps**:
  1. Flip `usePhysicsLayout` boolean
  2. Update button text + active class
  3. Call appropriate apply function
- **Called by**: Physics toggle button click

### 4. Event Binding (line 6645)
```javascript
document.getElementById('physics-toggle').addEventListener('click', togglePhysicsLayout);
```
- Executes inside script module (accessible scope)
- Calls `togglePhysicsLayout()` on button click

## Data Flow

### ON Physics Toggle Click:
```
togglePhysicsLayout()
  ├─ usePhysicsLayout = !usePhysicsLayout
  ├─ Update UI (button text + class)
  └─ If PHYSICS mode:
       └─ applyPhysicsForces()
           ├─ Graph.d3Force(...) reconfigurations
           └─ Graph.tickFrame()
     Else (TREE mode):
       └─ applyTreeLayout()
           ├─ calculateTreeLayout() (if not cached)
           ├─ Copy positions to nodes
           ├─ Clear all forces
           └─ Graph.tickFrame()
```

## Performance Considerations

- **Tree Calculation**: O(n + m) where n=nodes, m=links (BFS)
- **Caching**: Tree positions cached in `treeLayoutPositions` to avoid recalculation
- **Force Simulation**: D3 restart is lightweight (nodes already positioned)
- **Culling**: Performance culling continues to work in both modes

## Known Limitations

1. Tree root selection uses connectivity only (could improve with domain knowledge)
2. Tree spacing is uniform across levels (could use adaptive spacing)
3. No animation between layouts (instant switch)
4. External graphs (large, 2000+ nodes) may take longer for tree calculation

## Testing Checklist

- [ ] Load large graph (2792 nodes)
- [ ] Click PHYSICS button → toggles text to "TREE"
- [ ] Graph transitions to hierarchical tree layout
- [ ] Click TREE button → toggles text to "PHYSICS"
- [ ] Graph resumes force simulation
- [ ] No console errors on toggle
- [ ] Performance stays 60 FPS after toggle
- [ ] Hand tracking still works after toggle
- [ ] Camera controls responsive in both modes

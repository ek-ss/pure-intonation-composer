# Reference-Node Layered Grid Layout Specification

**Project:** Pure Intonation Composer
**Component:** Harmonic Graph Visualization
**Layout ID:** `reference_layered_grid`
**Version:** 0.1

---

## 1. Purpose

The reference-node layered grid layout provides a deterministic visualization of a Johnson graph or CPS combination graph relative to one selected reference node.

Nodes are arranged into horizontal layers according to the number of elements they share with the reference node.

The layout is intended to make the following properties visually explicit:

* distance from the reference harmonic state;
* number of shared CPS factors;
* one-element substitutions between adjacent states;
* possible random-walk transitions;
* harmonic continuity around the selected state.

This layout supplements force-directed graph layouts such as `spring_layout`, which may be visually clear but do not directly expose the combinatorial structure of the graph.

---

## 2. Applicable Graphs

The layout applies to graphs whose nodes are fixed-size combinations selected from a common source set.

Typical examples include:

* CPS graphs;
* Johnson graphs (J(n,k));
* Eikosany graphs based on CPS(6,3);
* harmonic-state graphs whose node identifiers preserve their generating combinations.

For a Johnson graph (J(n,k)):

* each node contains exactly (k) distinct elements;
* two nodes are adjacent when they share exactly (k-1) elements.

Example node:

```text
(1, 3, 5)
```

Example adjacent node:

```text
(1, 3, 7)
```

The two nodes share two of their three elements.

---

## 3. Inputs

The layout function accepts the following inputs.

### 3.1 Graph

```text
graph: nx.Graph
```

The graph must contain combination nodes represented as one of:

* tuple of integers;
* frozenset of integers;
* immutable node identifier with a `combination` node attribute.

Preferred canonical representation:

```text
tuple[int, ...]
```

Example:

```text
(1, 3, 5)
```

---

### 3.2 Reference Node

```text
reference_node: tuple[int, ...]
```

The node used as the origin of the layered structure.

The reference node must exist in the graph.

Example:

```text
(1, 3, 5)
```

---

### 3.3 Optional Layout Parameters

```text
horizontal_spacing: float = 1.5
vertical_spacing: float = 1.8
center_layers: bool = true
sort_mode: str = "lexicographic"
reference_on_top: bool = true
```

Optional rendering parameters may include:

```text
show_layer_labels: bool = true
show_edge_labels: bool = false
highlight_reference: bool = true
highlight_current_node: bool = true
```

---

## 4. Shared-Element Count

For every node (v), define its shared-element count with the reference node (r) as:

```text
shared(v, r) = |set(v) ∩ set(r)|
```

For (J(n,k)), the possible values are:

```text
0, 1, ..., k
```

The reference node itself has:

```text
shared(r, r) = k
```

Example for reference node `(1, 3, 5)`:

| Node         | Shared elements | Shared count |
| ------------ | --------------- | -----------: |
| `(1, 3, 5)`  | `{1,3,5}`       |            3 |
| `(1, 3, 7)`  | `{1,3}`         |            2 |
| `(1, 7, 9)`  | `{1}`           |            1 |
| `(7, 9, 11)` | `{}`            |            0 |

---

## 5. Layer Assignment

Each node is assigned to a horizontal layer according to its shared-element count.

For a CPS(6,3) or (J(6,3)) graph:

```text
Layer 3: reference node
Layer 2: nodes sharing two elements
Layer 1: nodes sharing one element
Layer 0: node sharing no elements
```

When `reference_on_top = true`, larger shared-element counts appear higher in the diagram.

The vertical coordinate is:

```text
y(v) = vertical_spacing × shared(v, reference)
```

An equivalent implementation may reverse or negate the vertical axis, provided that the reference layer remains visually identifiable as the origin layer.

Recommended convention:

```text
highest shared count → top
lowest shared count  → bottom
```

---

## 6. Relation to Johnson-Graph Distance

For a Johnson graph (J(n,k)), graph distance from the reference node is:

```text
distance(v, reference) = k - shared(v, reference)
```

Therefore, the layer assignment is also a breadth-first distance layering.

For (J(6,3)):

| Shared count | Graph distance |
| -----------: | -------------: |
|            3 |              0 |
|            2 |              1 |
|            1 |              2 |
|            0 |              3 |

The implementation may store both values as node metadata:

```json
{
  "shared_count": 2,
  "reference_distance": 1
}
```

For nonstandard graphs whose edges do not exactly follow the Johnson adjacency rule, shared count and shortest-path distance may differ. In such cases:

* vertical layers remain based on shared count;
* shortest-path distance should be calculated and displayed separately;
* the UI must not label shared-count layers as graph-distance layers unless equivalence has been verified.

---

## 7. Horizontal Ordering

Nodes within each layer must be ordered deterministically.

The default ordering is lexicographic:

```text
sort_mode = "lexicographic"
```

Example:

```text
(1, 3, 7)
(1, 3, 9)
(1, 3, 11)
(1, 5, 7)
...
```

Supported ordering modes should include:

### 7.1 Lexicographic

Sort by the full combination tuple.

```text
key(node) = node
```

This mode is stable, simple, and reproducible.

### 7.2 Product

Sort by the integer product of the node elements.

```text
key(node) = product(node)
```

This is useful for CPS visualization because it follows the unnormalized harmonic product.

### 7.3 Pitch

Sort by the octave-normalized pitch ratio or cent value associated with the node.

```text
key(node) = cents(node_ratio)
```

This mode provides a relationship between graph position and audible pitch.

### 7.4 Transition Group

Group nodes according to which reference element is removed and which new element is inserted.

Example transition from `(1,3,5)`:

```text
remove 5, add 7
remove 5, add 9
remove 3, add 7
...
```

This mode is useful for inspecting one-factor substitutions but may require additional spacing between groups.

---

## 8. Horizontal Coordinates

Let a layer contain (m) nodes after sorting.

When `center_layers = true`, the horizontal coordinates are centered around zero:

```text
x_i = horizontal_spacing × (i - (m - 1)/2)
```

where:

```text
i = 0, 1, ..., m-1
```

This places the middle of every layer on the same vertical axis.

Example for five nodes:

```text
-2s, -s, 0, s, 2s
```

where (s) is `horizontal_spacing`.

When `center_layers = false`:

```text
x_i = horizontal_spacing × i
```

Centered layers are the required default.

---

## 9. Position Output

The layout function returns a mapping compatible with NetworkX:

```python
dict[Node, tuple[float, float]]
```

Example:

```python
{
    (1, 3, 5): (0.0, 5.4),
    (1, 3, 7): (-4.5, 3.6),
    (1, 3, 9): (-3.0, 3.6),
    ...
}
```

The function must not mutate the graph unless metadata annotation is explicitly requested.

Recommended function signature:

```python
def reference_layered_grid_layout(
    graph: nx.Graph,
    reference_node: tuple[int, ...],
    *,
    horizontal_spacing: float = 1.5,
    vertical_spacing: float = 1.8,
    center_layers: bool = True,
    sort_mode: str = "lexicographic",
    reference_on_top: bool = True,
) -> dict[Hashable, tuple[float, float]]:
    ...
```

---

## 10. Node Labels

Each node should support multiple label modes.

### Combination Label

```text
{1,3,5}
```

### Product Label

```text
15
```

### Ratio Label

```text
15/8
```

### Combined Label

```text
{1,3,5}
15/8
```

The default label for CPS graph exploration is:

```text
combination + normalized ratio
```

Example:

```text
{1,3,5}
15/8
```

Long labels should be rendered on two lines.

---

## 11. Layer Labels

When enabled, each layer must display both shared count and reference distance.

Example for (J(6,3)):

```text
Shared 3 · Distance 0
Shared 2 · Distance 1
Shared 1 · Distance 2
Shared 0 · Distance 3
```

Layer labels should appear to the left of the leftmost node or along a dedicated vertical axis.

They must not overlap nodes or edges.

---

## 12. Edge Rendering

All graph edges remain visible unless filtering is enabled.

For a Johnson graph, most edges connect adjacent layers because one-element substitution changes the shared count by at most one.

Three edge classes may occur:

### Outward Edge

Moves farther from the reference.

```text
shared count decreases by 1
```

### Inward Edge

Moves toward the reference.

```text
shared count increases by 1
```

### Lateral Edge

Remains in the same shared-count layer.

```text
shared count unchanged
```

The layout must preserve lateral edges. They are important because states equally distant from the reference may still be adjacent.

Optional edge metadata:

```json
{
  "direction_relative_to_reference": "outward",
  "removed_element": 5,
  "added_element": 7
}
```

For an undirected graph, this direction is defined only relative to the chosen traversal or reference orientation.

---

## 13. Visual Encoding

Recommended default visual encoding:

| Element                  | Representation                    |
| ------------------------ | --------------------------------- |
| Reference node           | largest node with distinct border |
| Current random-walk node | highlighted node                  |
| Visited node             | increased opacity or marker       |
| Unvisited node           | normal node                       |
| Current path             | thicker edges                     |
| Other edges              | thin, partially transparent       |
| Layer                    | horizontal alignment              |
| Shared count             | vertical position                 |

Color must not be the only method used to identify the reference or current node. Size, border width, or marker shape should also differ for accessibility.

---

## 14. Interactive Behavior

The web interface should support:

* clicking a node to select it;
* double-clicking a node to make it the new reference;
* hovering to display combination, product, ratio, cent value, and graph distance;
* highlighting all adjacent nodes;
* highlighting the shortest path to the reference;
* playing the pitch or harmonic state associated with a node;
* animating a random walk through the graph.

When the reference node changes, the layout is recomputed.

The transition should be animated where possible so users can track how layers are reorganized.

---

## 15. Reference-Node Selection

The reference node may be selected by:

* explicit node ID;
* graph UI interaction;
* current harmonic state;
* start node of a random walk;
* lowest harmonic-complexity node;
* configured tonic or CPS center.

If no reference node is supplied, the implementation should use:

1. the configured tonic node, when available;
2. otherwise the lexicographically first node.

The selected fallback must be deterministic.

---

## 16. Harmonic and Subharmonic Views

The same combination graph may be used for both harmonic and subharmonic CPS interpretations.

The combinatorial positions remain unchanged because node combinations and adjacency are identical.

Only pitch-related labels change:

```text
Harmonic ratio:
normalize(product)

Subharmonic ratio:
normalize(1 / product)
```

The UI should support:

* harmonic mode;
* subharmonic mode;
* side-by-side labels;
* harmonic/subharmonic mirror comparison.

Switching between harmonic and subharmonic modes should not rearrange nodes unless `sort_mode = "pitch"` is active.

When pitch sorting is active, the UI should warn that switching mode may change horizontal node ordering.

---

## 17. CPS(6,3) Expected Structure

For CPS(6,3), the graph has:

```text
20 nodes
degree 9 for every node
90 edges
diameter 3
```

Relative to any reference node:

| Shared count | Number of nodes |
| -----------: | --------------: |
|            3 |               1 |
|            2 |               9 |
|            1 |               9 |
|            0 |               1 |

Therefore, the expected layered form is:

```text
            1 node

          9 nodes

          9 nodes

            1 node
```

This `1–9–9–1` symmetry is a key visual property of (J(6,3)) and must be preserved by the layout.

---

## 18. Validation Rules

The layout function must validate:

* the graph is not empty;
* the reference node exists;
* all combination nodes have the same size;
* combination nodes contain unique elements;
* spacing values are positive;
* the selected sort mode is supported.

For Johnson-graph-specific validation, it may additionally verify:

* every node has size (k);
* adjacent nodes share (k-1) elements;
* the graph is connected.

Invalid input must raise a descriptive exception.

Example:

```text
Reference node (1,3,13) does not exist in the graph.
```

---

## 19. Determinism

Given the same:

* graph;
* reference node;
* spacing;
* ordering mode;
* orientation;

the function must return identical coordinates.

The layout must not use random values.

This is required for:

* reproducible screenshots;
* regression testing;
* UI state restoration;
* stable node animation;
* deterministic exports.

---

## 20. Performance Requirements

For graphs up to 1,000 nodes:

```text
layout computation < 100 ms
```

under ordinary desktop conditions.

The implementation should use a single pass to group nodes by shared count, followed by sorting within each group.

Expected complexity:

```text
O(|V| × k + |V| log |V|)
```

Edge traversal is not required for the basic coordinate calculation.

---

## 21. Test Cases

### Test 1: CPS(6,3) Layer Sizes

Given:

```text
source set = {1,3,5,7,9,11}
reference = (1,3,5)
```

Expected layer sizes:

```text
shared 3 → 1
shared 2 → 9
shared 1 → 9
shared 0 → 1
```

### Test 2: Reference Position

The reference node must be centered in its layer:

```text
x = 0
```

### Test 3: Centered Layers

For each layer, the arithmetic mean of all x coordinates must be zero within floating-point tolerance.

### Test 4: Stable Ordering

Repeated calls with identical inputs must return identical coordinates.

### Test 5: Distance Equivalence

For a valid Johnson graph:

```text
shortest_path_length(reference, node)
=
k - shared_count(reference, node)
```

### Test 6: Harmonic/Subharmonic Stability

Switching ratio interpretation without pitch-based sorting must preserve all coordinates.

---

## 22. Acceptance Criteria

The feature is complete when:

* a valid CPS or Johnson graph can be rendered using the layout;
* the reference node is visually isolated in the highest layer;
* nodes are correctly grouped by shared-element count;
* all layers are horizontally centered;
* ordering is deterministic;
* graph edges remain visible;
* current and reference nodes can be highlighted independently;
* CPS(6,3) produces the expected `1–9–9–1` arrangement;
* unit tests cover grouping, ordering, validation, and determinism;
* harmonic and subharmonic label modes are supported.

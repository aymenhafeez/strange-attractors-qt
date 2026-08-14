# strange-attractors-qt

PyQtGraph app for visualising strange attractors.

<table>
  <tr>
    <td><img src="media/image_7.png" /></td>
    <td><img src="media/image_8.png" /></td>
  </tr>
  <tr>
    <td><img src="media/image_4.png" /></td>
    <td><img src="media/image_9.png" /></td>
  </tr>
</table>

This is a local, more performant version of
[strange-attractor-visualiser](https://github.com/aymenhafeez/strange-attractor-visualiser)

## Current features

* Selection of attractors with real time slider updates for parameters
* Input custom time dependant ODE systems
* Trajectory animation
* 2D heatmap projections
* Multi trajectory view with varying initial conditions
* Lyapunov exponent spectrum, convergence plots and Kaplan-Yorke dimension
* Bifuraction diagrams
* Poincaré section view with configurable section plane
* Save and load attractor configurations
* Integrated scripting panel and Jupyter console

## Running the app

```bash
git clone https://github.com/aymenhafeez/strange-attractors-qt
cd stange-attractors-qt
```

With uv:

```bash
uv sync
uv run analysis  # --fullscreen
```

## Development

```bash
uv sync
uv run analysis
```

Run tests:

```bash
uv run pytest -v
```

Enable performance logging (outputs attractor and lyapunov solve times):

```bash
ANALYSIS_PROFILE=1 uv run analysis
```

## TODO

* Extend expression parser to accept non strange attractor like systems
* Parametric system plotting

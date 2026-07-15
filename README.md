# strange-attractors-qt

PyQtGraph app for visualising strange attractors.

<table>
  <tr>
    <td><img src="media/image_7.png" /></td>
    <td><video src="media/video_1.mp4" autoplay loop muted playsinline width="100%"></video></td>
  </tr>
  <tr>
    <td><img src="media/image_4.png" /></td>
    <td><img src="media/image_6.png" /></td>
  </tr>
</table>

This is a local, more performant version of
[strange-attractor-visualiser](https://github.com/aymenhafeez/strange-attractor-visualiser)

## Current features

* Selection of attractors with real time slider updates for parameters
* Input custom attractor equations
* Scatter and line rendering modes
* Trajectory animation
* Trail mode showing solution's time step evolution
* 2D heatmap projections
* Multi trajectory view with varying initial conditions
* Lyapunov exponent spectrum, convergence plots and Kaplan-Yorke dimension
* Bifuraction plot from Poincaré sweep
* Poincaré section view with configurable section plane

## Running the app

```
git clone https://github.com/aymenhafeez/strange-attractors-qt
cd strange-attractors-qt
```

With uv:

```
uv sync
uv run strange-attractors
```

With pip:

```
pip install -e .
python -m src.attractors
```

Optionally use the `--fullscreen` flag to launch the app in fullscreen mode.

## TODO

* Improve Bifuraction performance
* Extend expression parser to accept non strange attractor like systems
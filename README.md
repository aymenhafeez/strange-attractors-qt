# strange-attractors-qt

PyQtGraph app for visualising strange attractors.

<table>
  <tr>
    <td><img src="media/image_3.png" /></td>
    <td><img src="media/image_5.gif" /></td>
  </tr>
  <tr>
    <td><img src="media/image_4.png" /></td>
    <td><img src="media/image_6.png" /></td>
  </tr>
</table>

This is a local, more performant version of
[strange-attractor-visualiser](https://github.com/aymenhafeez/strange-attractor-visualiser)

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

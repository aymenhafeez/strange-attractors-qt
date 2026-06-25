from .app import Window
import pyqtgraph as pg


def main():
    app = pg.mkQApp()
    app.setStyle("Fusion")
    w = Window()
    w.resize(1100, 800)
    w.show()
    pg.exec()


if __name__ == "__main__":
    main()

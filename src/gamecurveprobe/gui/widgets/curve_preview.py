from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from gamecurveprobe.models import CurvePoint


class CurvePreviewWidget(QWidget):
    """Lightweight custom curve renderer to avoid a QtCharts dependency."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._points: list[CurvePoint] = []
        self.setMinimumHeight(220)

    def set_points(self, points: list[CurvePoint]) -> None:
        self._points = points
        self.update()

    def set_title(self, title: str) -> None:
        self._title = title
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(12, 12, -12, -12)

        painter.fillRect(rect, QColor("#131a23"))
        painter.setPen(QPen(QColor("#2c3948"), 1))
        for index in range(6):
            x = rect.left() + rect.width() * index / 5
            y = rect.top() + rect.height() * index / 5
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        painter.setPen(QColor("#eef4fb"))
        painter.drawText(rect.adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self._title)

        if not self._points:
            painter.setPen(QColor("#7a8aa0"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No curve data yet")
            return

        plot = rect.adjusted(28, 36, -18, -28)
        path = QPainterPath()
        max_y = max(point.normalized_speed for point in self._points) or 1.0

        for index, point in enumerate(self._points):
            x = plot.left() + plot.width() * point.input_value
            y_value = point.normalized_speed / max_y
            y = plot.bottom() - plot.height() * y_value
            if index == 0:
                path.moveTo(QPointF(x, y))
            else:
                path.lineTo(QPointF(x, y))

        painter.setPen(QPen(QColor("#54b5ff"), 2.5))
        painter.drawPath(path)

        painter.setPen(QPen(QColor("#8fd19e"), 1.5))
        for point in self._points:
            x = plot.left() + plot.width() * point.input_value
            y_value = point.normalized_speed / max_y
            y = plot.bottom() - plot.height() * y_value
            painter.drawEllipse(QPointF(x, y), 3.0, 3.0)

        painter.setPen(QColor("#7a8aa0"))
        painter.drawText(QRectF(plot.left(), plot.bottom() + 4, plot.width(), 20), Qt.AlignmentFlag.AlignRight, "input")
        painter.save()
        painter.translate(rect.left() + 4, plot.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-40, -10, 80, 20), Qt.AlignmentFlag.AlignCenter, "speed")
        painter.restore()

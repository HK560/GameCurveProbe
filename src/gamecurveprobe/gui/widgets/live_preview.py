from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from gamecurveprobe.models import RoiRect
from gamecurveprobe.vision.motion_estimator import MotionEstimate


class LivePreviewWidget(QWidget):
    """Display a live frame and allow drag-to-select ROI."""

    roi_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(280)
        self._pixmap: QPixmap | None = None
        self._frame_size: tuple[int, int] | None = None
        self._roi: RoiRect | None = None
        self._drag_origin: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._status_text = "Select a target window to start preview."
        self._motion: MotionEstimate | None = None

    def set_frame(self, frame: np.ndarray | None) -> None:
        if frame is None:
            self._pixmap = None
            self._frame_size = None
            self.update()
            return

        height, width, channels = frame.shape
        bytes_per_line = channels * width
        image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._frame_size = (width, height)
        self.update()

    def set_roi(self, roi: RoiRect | None) -> None:
        self._roi = roi
        self.update()

    def set_status(self, text: str) -> None:
        self._status_text = text
        self.update()

    def set_motion(self, motion: MotionEstimate | None) -> None:
        self._motion = motion
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self._frame_size = None
        self._motion = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None:
            return
        if not self._image_rect().contains(event.position().toPoint()):
            return
        self._drag_origin = event.position().toPoint()
        self._drag_current = self._drag_origin
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_origin is None:
            return
        self._drag_current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_origin is None or self._drag_current is None or self._frame_size is None:
            self._drag_origin = None
            self._drag_current = None
            return

        selection = QRect(self._drag_origin, self._drag_current).normalized()
        self._drag_origin = None
        self._drag_current = None
        roi = self._widget_rect_to_frame(selection)
        if roi is not None:
            self._roi = roi
            self.roi_changed.emit(roi)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101720"))

        if self._pixmap is None:
            painter.setPen(QColor("#7f97b3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._status_text)
            return

        image_rect = self._image_rect()
        painter.drawPixmap(image_rect, self._pixmap)

        if self._roi is not None:
            painter.setPen(QPen(QColor("#54b5ff"), 2))
            painter.drawRect(self._frame_rect_to_widget(self._roi))

        if self._drag_origin is not None and self._drag_current is not None:
            painter.setPen(QPen(QColor("#ffb454"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self._drag_origin, self._drag_current).normalized())

        painter.fillRect(QRect(12, 12, 360, 54), QColor(12, 17, 23, 190))
        painter.setPen(QColor("#e8f1fa"))
        motion_line = self._status_text
        if self._motion is not None:
            motion_line = (
                f"{self._status_text}\n"
                f"vx {self._motion.px_per_sec_x:8.1f}px/s  "
                f"vy {self._motion.px_per_sec_y:8.1f}px/s  "
                f"pts {self._motion.tracked_points:3d}  "
                f"conf {self._motion.confidence:.2f}"
            )
        painter.drawText(QRect(20, 18, 340, 42), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, motion_line)

    def _image_rect(self) -> QRect:
        if self._pixmap is None:
            return QRect()
        area = self.rect().adjusted(12, 12, -12, -12)
        pixmap_size = self._pixmap.size()
        scaled = pixmap_size.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
        left = area.left() + (area.width() - scaled.width()) // 2
        top = area.top() + (area.height() - scaled.height()) // 2
        return QRect(left, top, scaled.width(), scaled.height())

    def _widget_rect_to_frame(self, rect: QRect) -> RoiRect | None:
        if self._frame_size is None:
            return None
        image_rect = self._image_rect()
        clipped = rect.intersected(image_rect)
        if clipped.width() < 8 or clipped.height() < 8:
            return None
        frame_width, frame_height = self._frame_size
        scale_x = frame_width / image_rect.width()
        scale_y = frame_height / image_rect.height()
        x = int((clipped.left() - image_rect.left()) * scale_x)
        y = int((clipped.top() - image_rect.top()) * scale_y)
        width = int(clipped.width() * scale_x)
        height = int(clipped.height() * scale_y)
        return RoiRect(x=x, y=y, width=width, height=height)

    def _frame_rect_to_widget(self, roi: RoiRect) -> QRect:
        if self._frame_size is None:
            return QRect()
        image_rect = self._image_rect()
        frame_width, frame_height = self._frame_size
        scale_x = image_rect.width() / frame_width
        scale_y = image_rect.height() / frame_height
        return QRect(
            image_rect.left() + int(roi.x * scale_x),
            image_rect.top() + int(roi.y * scale_y),
            max(1, int(roi.width * scale_x)),
            max(1, int(roi.height * scale_y)),
        )

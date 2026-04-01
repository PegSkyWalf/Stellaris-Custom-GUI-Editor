"""
阵列与镜像操作对话框。

提供线性阵列、圆形阵列、镜像三种操作的参数输入界面。
"""
from __future__ import annotations

import math

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QGroupBox, QCheckBox, QDialogButtonBox,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsRectItem,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QBrush, QColor

from ..core.theme_manager import ThemeManager


class LinearArrayDialog(QDialog):
    """线性阵列参数对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('线性阵列')
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 50)
        self._count_spin.setValue(3)
        self._count_spin.setToolTip('复制数量（不含原件）')
        form.addRow('复制数量:', self._count_spin)

        self._offset_x_spin = QSpinBox()
        self._offset_x_spin.setRange(-2000, 2000)
        self._offset_x_spin.setValue(50)
        self._offset_x_spin.setSuffix(' px')
        form.addRow('X 偏移:', self._offset_x_spin)

        self._offset_y_spin = QSpinBox()
        self._offset_y_spin.setRange(-2000, 2000)
        self._offset_y_spin.setValue(0)
        self._offset_y_spin.setSuffix(' px')
        form.addRow('Y 偏移:', self._offset_y_spin)

        layout.addLayout(form)

        hint = QLabel('每个副本相对前一个偏移指定像素。')
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9pt;')
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def count(self) -> int:
        return self._count_spin.value()

    @property
    def offset_x(self) -> int:
        return self._offset_x_spin.value()

    @property
    def offset_y(self) -> int:
        return self._offset_y_spin.value()


class CircularArrayDialog(QDialog):
    """圆形阵列参数对话框 — 支持两种模式 + 实时预览。"""

    def __init__(self, center_x: float = 960, center_y: float = 540, parent=None):
        super().__init__(parent)
        self.setWindowTitle('圆形阵列')
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()

        # 左侧：参数
        form_group = QGroupBox('参数')
        self._form = QFormLayout(form_group)
        form = self._form

        self._mode_combo = QComboBox()
        self._mode_combo.addItem('以控件为圆心 — 副本分布在外环', 'center')
        self._mode_combo.addItem('控件在环上 — 作为起点，与副本闭合成环', 'on_ring')
        form.addRow('模式:', self._mode_combo)

        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 36)
        self._count_spin.setValue(4)
        self._count_spin.setToolTip('新建副本数量')
        form.addRow('副本数量:', self._count_spin)

        # 圆心字段 (仅 on_ring 模式需要)
        self._cx_label = QLabel('圆心 X:')
        self._center_x_spin = QDoubleSpinBox()
        self._center_x_spin.setRange(-4000, 8000)
        self._center_x_spin.setDecimals(0)
        self._center_x_spin.setValue(center_x)
        self._center_x_spin.setSuffix(' px')
        form.addRow(self._cx_label, self._center_x_spin)

        self._cy_label = QLabel('圆心 Y:')
        self._center_y_spin = QDoubleSpinBox()
        self._center_y_spin.setRange(-4000, 8000)
        self._center_y_spin.setDecimals(0)
        self._center_y_spin.setValue(center_y)
        self._center_y_spin.setSuffix(' px')
        form.addRow(self._cy_label, self._center_y_spin)

        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(1, 4000)
        self._radius_spin.setDecimals(0)
        self._radius_spin.setValue(120)
        self._radius_spin.setSuffix(' px')
        self._radius_spin.setToolTip('副本到圆心的距离（像素）')
        form.addRow('半径:', self._radius_spin)

        top_layout.addWidget(form_group, 1)

        # 右侧：预览
        preview_group = QGroupBox('预览')
        preview_layout = QVBoxLayout(preview_group)
        self._preview_scene = QGraphicsScene()
        self._preview_view = QGraphicsView(self._preview_scene)
        self._preview_view.setFixedSize(200, 200)
        from PySide6.QtGui import QPainter
        self._preview_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._preview_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._preview_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_layout.addWidget(self._preview_view)
        top_layout.addWidget(preview_group, 0)

        layout.addLayout(top_layout)

        self._hint = QLabel('')
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9pt;')
        layout.addWidget(self._hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 连接信号以更新预览
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._count_spin.valueChanged.connect(self._update_preview)
        self._radius_spin.valueChanged.connect(self._update_preview)
        self._on_mode_changed()  # 初始化字段可见性和预览

    def _on_mode_changed(self):
        """切换模式时显示/隐藏圆心字段。"""
        is_on_ring = (self._mode_combo.currentData() == 'on_ring')
        self._cx_label.setVisible(is_on_ring)
        self._center_x_spin.setVisible(is_on_ring)
        self._cy_label.setVisible(is_on_ring)
        self._center_y_spin.setVisible(is_on_ring)
        self._update_preview()

    def _update_preview(self):
        """更新预览画布。"""
        self._preview_scene.clear()
        mode = self._mode_combo.currentData()
        count = self._count_spin.value()
        radius_val = self._radius_spin.value()

        # 预览坐标系：以 (100, 100) 为中心，缩放到 200×200 区域
        cx, cy = 100, 100
        r = min(radius_val, 80) if radius_val > 0 else 60  # 预览半径

        # 绘制圆形轨迹
        orbit_pen = QPen(QColor(ThemeManager.accent_color()), 1, Qt.PenStyle.DashLine)
        self._preview_scene.addEllipse(
            cx - r, cy - r, 2 * r, 2 * r, orbit_pen)

        # 绘制圆心标记
        cross_pen = QPen(QColor(ThemeManager.muted_color()), 1)
        self._preview_scene.addLine(cx - 4, cy, cx + 4, cy, cross_pen)
        self._preview_scene.addLine(cx, cy - 4, cx, cy + 4, cross_pen)

        item_size = 12

        if mode == 'center':
            # 原件在圆心，副本在环上
            orig_brush = QBrush(QColor(ThemeManager.accent_color()))
            orig_rect = self._preview_scene.addRect(
                cx - item_size / 2, cy - item_size / 2, item_size, item_size,
                QPen(Qt.PenStyle.NoPen), orig_brush)

            copy_color = QColor(ThemeManager.fg_color())
            copy_color.setAlpha(180)
            copy_brush = QBrush(copy_color)
            angle_step = 2 * math.pi / max(count, 1)
            for i in range(count):
                a = angle_step * i
                px = cx + r * math.cos(a) - item_size / 2
                py = cy + r * math.sin(a) - item_size / 2
                self._preview_scene.addRect(
                    px, py, item_size, item_size,
                    QPen(Qt.PenStyle.NoPen), copy_brush)

            self._hint.setText(
                f'选中控件保持在原位（圆心），在环上创建 {count} 个副本。')
        else:  # on_ring
            total = count + 1
            angle_step = 2 * math.pi / total

            # 原件 = 第一个位置
            orig_brush = QBrush(QColor(ThemeManager.accent_color()))
            a0 = 0
            px0 = cx + r * math.cos(a0) - item_size / 2
            py0 = cy + r * math.sin(a0) - item_size / 2
            self._preview_scene.addRect(
                px0, py0, item_size, item_size,
                QPen(Qt.PenStyle.NoPen), orig_brush)

            copy_color = QColor(ThemeManager.fg_color())
            copy_color.setAlpha(180)
            copy_brush = QBrush(copy_color)
            for i in range(1, total):
                a = angle_step * i
                px = cx + r * math.cos(a) - item_size / 2
                py = cy + r * math.sin(a) - item_size / 2
                self._preview_scene.addRect(
                    px, py, item_size, item_size,
                    QPen(Qt.PenStyle.NoPen), copy_brush)

            self._hint.setText(
                f'选中控件在环上作为起点，创建 {count} 个副本，'
                f'共 {total} 个均匀分布在环上。')

        self._preview_view.fitInView(
            QRectF(-10, -10, 220, 220), Qt.AspectRatioMode.KeepAspectRatio)

    @property
    def count(self) -> int:
        return self._count_spin.value()

    @property
    def center_x(self) -> float:
        return self._center_x_spin.value()

    @property
    def center_y(self) -> float:
        return self._center_y_spin.value()

    @property
    def radius(self) -> float:
        return self._radius_spin.value()

    @property
    def mode(self) -> str:
        return self._mode_combo.currentData()


class MirrorDialog(QDialog):
    """镜像操作参数对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('镜像')
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._axis_combo = QComboBox()
        self._axis_combo.addItem('垂直轴（左右翻转）', 'v')
        self._axis_combo.addItem('水平轴（上下翻转）', 'h')
        form.addRow('镜像轴:', self._axis_combo)

        self._copy_check = QCheckBox('保留原件（镜像复制）')
        self._copy_check.setChecked(True)
        form.addRow(self._copy_check)

        layout.addLayout(form)

        hint = QLabel('围绕选中控件的集合中心进行镜像。\n群星不支持旋转/翻转，仅改变位置。')
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9pt;')
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def axis(self) -> str:
        return self._axis_combo.currentData()

    @property
    def copy_mode(self) -> bool:
        return self._copy_check.isChecked()

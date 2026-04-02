"""
首次启动向导 — 在用户第一次打开应用时引导完成基础配置。

共 4 步：
  1. 欢迎页
  2. 自动检测 / 手动指定游戏目录
  3. 选择界面主题
  4. 完成与快速上手提示
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QButtonGroup, QRadioButton,
    QFrame, QStackedWidget, QWidget, QScrollArea,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QLinearGradient

from ..core.settings import AppSettings
from ..core.theme_manager import AVAILABLE_THEMES, ThemeManager, DEFAULT_THEME
from ..core.i18n import _


# ---------------------------------------------------------------------------
# 小工具：生成主题预览色块
# ---------------------------------------------------------------------------

def _theme_preview_pixmap(theme: str, w: int = 80, h: int = 50) -> QPixmap:
    pm = QPixmap(w, h)
    if theme == 'light':
        bg, bar, accent = QColor('#f0f0f0'), QColor('#e0e0e0'), QColor('#0e639c')
    elif theme == 'dark_blue':
        bg, bar, accent = QColor('#12203a'), QColor('#1a2d4a'), QColor('#5bc0de')
    else:
        bg, bar, accent = QColor('#1e1e1e'), QColor('#252525'), QColor('#4a9fd4')

    pm.fill(bg)
    p = QPainter(pm)
    p.fillRect(0, 0, w, 14, bar)
    p.fillRect(4, 4, 30, 6, accent)
    p.fillRect(0, h - 12, w, 12, bar)
    p.setPen(QColor('#888888'))
    p.drawRect(0, 0, w - 1, h - 1)
    p.end()
    return pm


# ---------------------------------------------------------------------------
# 向导对话框
# ---------------------------------------------------------------------------

class WelcomeDialog(QDialog):
    """
    首次启动向导。
    调用 exec() 后可从 settings 读取用户已保存的选择。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = AppSettings.instance()
        self.setWindowTitle(_('欢迎使用 — 群星 GUI 编辑器'))
        self.setMinimumSize(560, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部渐变标题栏
        self._header = QLabel()
        self._header.setFixedHeight(72)
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._header)

        # 步骤堆叠
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # 底部按钮行
        btn_frame = QFrame()
        btn_frame.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(btn_frame)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(16, 8, 16, 8)
        self._step_label = QLabel('')
        self._step_label.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        btn_row.addWidget(self._step_label)
        btn_row.addStretch()
        self._back_btn = QPushButton(_('上一步'))
        self._back_btn.setFixedWidth(80)
        self._back_btn.clicked.connect(self._go_back)
        btn_row.addWidget(self._back_btn)
        self._next_btn = QPushButton(_('下一步 →'))
        self._next_btn.setFixedWidth(100)
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self._next_btn)
        layout.addLayout(btn_row)

        # 构建各步骤页面
        self._pages = [
            self._build_page_welcome(),
            self._build_page_game_dir(),
            self._build_page_theme(),
            self._build_page_finish(),
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        self._current = 0
        self._update_nav()

    # ------------------------------------------------------------------
    # 页面构建
    # ------------------------------------------------------------------

    def _build_page_welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 20)
        lay.setSpacing(14)

        title = QLabel(_('欢迎使用群星 GUI 编辑器！'))
        title.setFont(QFont('Microsoft YaHei', 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        desc = QLabel(_(
            '本编辑器帮助您为群星游戏模组设计可视化 GUI 界面，\n'
            '无需手动编写繁琐的脚本代码。\n\n'
            '接下来只需 3 步即可完成初始配置，随时可在\n'
            '【工具 → 设置】中修改这些选项。'
        ))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet('font-size:11px; line-height:1.6;')
        lay.addWidget(desc)

        features = QLabel(_(
            '•  可视化拖拽控件布局\n'
            '•  实时精灵图（DDS/PNG）渲染\n'
            '•  自动生成 .gui 脚本代码\n'
            '•  本地化文本预览\n'
            '•  撤销 / 重做 / 自动保存'
        ))
        features.setAlignment(Qt.AlignmentFlag.AlignCenter)
        features.setStyleSheet(f'font-size:10px; color:{ThemeManager.accent_color()};')
        lay.addWidget(features)
        lay.addStretch()
        return w

    def _build_page_game_dir(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(10)

        title = QLabel(_('步骤 1 / 3　指定游戏安装目录'))
        title.setFont(QFont('Microsoft YaHei', 13, QFont.Weight.Bold))
        lay.addWidget(title)

        desc = QLabel(_(
            '编辑器需要读取群星游戏文件（精灵图、脚本等）来提供预览功能。\n'
            '请指定群星的安装目录，例如：\n'
            '  Steam → 右键群星 → 管理 → 浏览本地文件'
        ))
        desc.setWordWrap(True)
        desc.setStyleSheet(f'font-size:10px; color:{ThemeManager.muted_color()};')
        lay.addWidget(desc)

        path_row = QHBoxLayout()
        self._game_dir_edit = QLineEdit()
        self._game_dir_edit.setPlaceholderText(_('游戏安装目录路径…'))
        path_row.addWidget(self._game_dir_edit)
        browse_btn = QPushButton(_('浏览…'))
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse_game_dir)
        path_row.addWidget(browse_btn)
        lay.addLayout(path_row)

        auto_btn = QPushButton(_('自动检测游戏目录'))
        auto_btn.clicked.connect(self._auto_detect)
        lay.addWidget(auto_btn)

        self._game_dir_status = QLabel('')
        self._game_dir_status.setWordWrap(True)
        self._game_dir_status.setStyleSheet('font-size:9px;')
        lay.addWidget(self._game_dir_status)

        skip_note = QLabel(_('如果暂时没有游戏目录，可点击"下一步"跳过，之后在设置中补填。'))
        skip_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        skip_note.setWordWrap(True)
        lay.addWidget(skip_note)

        # 尝试自动填写
        if self._settings.game_dir:
            self._game_dir_edit.setText(self._settings.game_dir)
        else:
            detected = self._settings.detect_game_dir()
            if detected:
                self._game_dir_edit.setText(detected)
                self._game_dir_status.setText(
                    _('[OK] 已自动检测到游戏目录'))
                self._game_dir_status.setStyleSheet('color:#2ecc71; font-size:9px;')

        lay.addStretch()
        return w

    def _build_page_theme(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(10)

        title = QLabel(_('步骤 2 / 3　选择界面主题'))
        title.setFont(QFont('Microsoft YaHei', 13, QFont.Weight.Bold))
        lay.addWidget(title)

        desc = QLabel(_('选择您偏好的界面配色方案，可在"工具→设置→外观"中随时更改。'))
        desc.setStyleSheet(f'font-size:10px; color:{ThemeManager.muted_color()};')
        desc.setWordWrap(True)
        lay.addWidget(desc)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(16)
        self._theme_group = QButtonGroup(self)
        current_theme = self._settings.theme or DEFAULT_THEME

        for key, (display_name, _) in AVAILABLE_THEMES.items():
            col = QVBoxLayout()
            col.setSpacing(4)

            preview = QLabel()
            pm = _theme_preview_pixmap(key, 100, 60)
            preview.setPixmap(pm)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(preview)

            rb = QRadioButton(display_name)
            rb.setProperty('theme_key', key)
            if key == current_theme:
                rb.setChecked(True)
            self._theme_group.addButton(rb)
            col.addWidget(rb, 0, Qt.AlignmentFlag.AlignHCenter)

            container = QWidget()
            container.setLayout(col)
            theme_row.addWidget(container)

        lay.addLayout(theme_row)
        lay.addStretch()
        return w

    def _build_page_finish(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(14)

        title = QLabel(_('步骤 3 / 3　配置完成！'))
        title.setFont(QFont('Microsoft YaHei', 14, QFont.Weight.Bold))
        lay.addWidget(title)

        tips = QLabel(_(
            '快速上手：\n\n'
            '1.  打开模组目录\n'
            '    文件 → 打开模组目录 → 选择你的 mod 文件夹\n\n'
            '2.  新建或打开 GUI 文件\n'
            '    文件 → 新建 GUI 文件（或打开已有 .gui / .guicore）\n\n'
            '3.  从"控件库"拖入控件，在"属性面板"编辑\n\n'
            '4.  保存（Ctrl+S）生成 .gui 脚本\n\n'
            '如有问题，请查看帮助文档或到 GitHub 提交 Issue。'
        ))
        tips.setWordWrap(True)
        tips.setStyleSheet('font-size:10px; line-height:1.7;')
        lay.addWidget(tips)
        lay.addStretch()
        return w

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------

    def _update_nav(self):
        total = len(self._pages)
        self._step_label.setText(_('第 ') + str(self._current + 1) + _(' 步，共 ') + str(total) + _(' 步'))
        self._back_btn.setEnabled(self._current > 0)
        if self._current == total - 1:
            self._next_btn.setText(_('开始使用'))
        else:
            self._next_btn.setText(_('下一步 →'))

    def _go_next(self):
        if self._current == len(self._pages) - 1:
            self._save_and_accept()
            return
        self._save_current_page()
        self._current += 1
        self._stack.setCurrentIndex(self._current)
        self._update_nav()

    def _go_back(self):
        if self._current > 0:
            self._current -= 1
            self._stack.setCurrentIndex(self._current)
            self._update_nav()

    def _save_current_page(self):
        """在离开页面时保存当前页的设置。"""
        if self._current == 1:
            game_dir = self._game_dir_edit.text().strip()
            if game_dir and os.path.isdir(game_dir):
                self._settings.game_dir = game_dir

        elif self._current == 2:
            checked = self._theme_group.checkedButton()
            if checked:
                theme_key = checked.property('theme_key')
                self._settings.theme = theme_key

    def _save_and_accept(self):
        self._save_current_page()
        self._settings.first_run = False
        self.accept()

    # ------------------------------------------------------------------
    # 游戏目录检测
    # ------------------------------------------------------------------

    def _browse_game_dir(self):
        start = self._game_dir_edit.text() or os.path.expanduser('~')
        path = QFileDialog.getExistingDirectory(self, _('选择群星游戏安装目录'), start)
        if path:
            self._game_dir_edit.setText(path)
            self._validate_game_dir(path)

    def _auto_detect(self):
        detected = self._settings.detect_game_dir()
        if detected:
            self._game_dir_edit.setText(detected)
            self._game_dir_status.setText(_('[OK] 已自动检测到游戏目录'))
            self._game_dir_status.setStyleSheet('color:#2ecc71; font-size:9px;')
        else:
            self._game_dir_status.setText(_(
                '✗ 未能自动检测到游戏目录，请手动浏览指定。\n'
                '提示：在 Steam 中右键群星 → 管理 → 浏览本地文件'
            ))
            self._game_dir_status.setStyleSheet('color:#e74c3c; font-size:9px;')

    def _validate_game_dir(self, path: str):
        if os.path.isdir(os.path.join(path, 'interface')):
            self._game_dir_status.setText(_('[OK] 路径有效（检测到 interface 目录）'))
            self._game_dir_status.setStyleSheet('color:#2ecc71; font-size:9px;')
        else:
            self._game_dir_status.setText(_('[!] 未检测到 interface 子目录，请确认路径正确'))
            self._game_dir_status.setStyleSheet('color:#f39c12; font-size:9px;')

"""展开态面板（M2）：按游戏分组的兑换码列表，一键复制 / 右键本地标记。

红线：不做任何网络/文件 IO——刷新意图经 refreshRequested、标记意图经
markRequested 交 CodeService 处理；数据由 WidgetWindow 推送
（写剪贴板属于 UI 职责，不算业务 IO）。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMenu,
                               QPushButton, QScrollArea, QSizeGrip,
                               QVBoxLayout, QWidget)

from ..core.models import (STATUS_EXPIRED_LOCAL, STATUS_NONE, STATUS_REDEEMED,
                           CodeItem)

GAME_ORDER = ["genshin", "hsr", "ww", "zzz"]
# 深色面板底(#182230)上的高对比配色（WCAG AA：正文≥4.5:1）。
# 文字用同色相浅色调（Material 深色主题：强调色取浅化去饱和 tint）；
# 徽章底为同色相低透明 rgba。注意：Qt QSS 的 8 位 hex 是 #AARRGGBB，
# 禁用 web 风格 #RRGGBBAA（v0.1.0 早期徽章串色即此因）。
GAME_COLORS = {"genshin": "#7DDCF5", "hsr": "#CDBBFF",
               "ww": "#93E6B4", "zzz": "#FFD98A"}
GAME_RGB = {"genshin": (78, 201, 225), "hsr": (157, 123, 255),
            "ww": (95, 208, 138), "zzz": (244, 211, 94)}

EXPANDED_SIZE = (420, 580)
MIN_EXPANDED_SIZE = (400, 460)
COLLAPSED_SIZE = (300, 300)   # 由 widget.py 实际计算，这里仅作默认参考

META_MAX_WIDTH = 200          # 描述标签换行宽度（与 setMaximumWidth 保持一致）
META_LINE_HEIGHT = 15         # 11px 字号的单行高估算
CODE_HEIGHT = 20              # 码标签单行高估算

BTN_QSS = ("QPushButton{color:#BFD7E8;background:#2E4258;border:none;"
           "border-radius:6px;font-size:12px;}"
           "QPushButton:hover{background:#3C5A78;}")


def game_color(game_id: str) -> str:
    return GAME_COLORS.get(game_id, "#A8BDD3")


def badge_qss(game_id: str) -> str:
    """徽章：浅色文字 + 同色相低透明底 + 细描边（组件边界≥3:1）。"""
    r, g, b = GAME_RGB.get(game_id, (168, 189, 211))
    return (f"color:{game_color(game_id)};"
            f"background:rgba({r},{g},{b},36);"
            f"border:1px solid rgba({r},{g},{b},90);"
            "border-radius:6px;padding:1px 6px;font-size:11px;font-weight:700;")


class ExpandedPanel(QWidget):
    """深色半透明圆角面板：头部（标题/状态/收起/刷新）+ 分组滚动列表。"""

    refreshRequested = Signal()
    collapseRequested = Signal()          # 返回收起态（小肥鱼）
    markRequested = Signal(str, object)   # uid, status|None

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMinimumSize(*MIN_EXPANDED_SIZE)
        self._items: list[CodeItem] = []
        self._open_state: dict[str, bool] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("兑了么 · 兑换码")
        title.setStyleSheet(
            "color:#EAF4FB;font-size:14px;font-weight:700;background:transparent;")
        self._status = QLabel("● 就绪")
        self._status.setStyleSheet("color:#A8BDD3;font-size:11px;background:transparent;")
        collapse = QPushButton("收起")
        collapse.setFixedSize(52, 24)
        collapse.setToolTip("返回小肥鱼（Esc / 双击面板空白处）")
        collapse.setStyleSheet(BTN_QSS)
        collapse.clicked.connect(self.collapseRequested.emit)
        refresh = QPushButton("刷新")
        refresh.setFixedSize(52, 24)
        refresh.setStyleSheet(BTN_QSS)
        refresh.clicked.connect(self.refreshRequested.emit)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._status)
        header.addSpacing(8)
        header.addWidget(collapse)
        header.addWidget(refresh)
        lay.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;}"
            "QScrollBar:vertical{background:transparent;width:8px;margin:0;}"
            "QScrollBar::handle:vertical{background:#3C5A78;border-radius:4px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}")
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(2)
        self._scroll.setWidget(body)
        lay.addWidget(self._scroll, 1)

        self._grip = QSizeGrip(self)   # 右下角拖拽调整面板大小（记忆于 config）

    def resizeEvent(self, e) -> None:
        self._grip.setGeometry(self.width() - 16, self.height() - 16, 16, 16)
        self._grip.raise_()

    # ---------- 外观 ----------
    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 14, 14)
        p.fillPath(path, QColor(24, 34, 48, 242))

    def mouseDoubleClickEvent(self, e) -> None:
        """面板任意空白处双击 = 返回收起态（与双击小肥鱼互为逆操作）。"""
        self.collapseRequested.emit()

    # ---------- 数据 ----------
    def set_status(self, text: str, color: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(
            f"color:{color};font-size:11px;background:transparent;")

    def set_items(self, items: list[CodeItem]) -> None:
        self._items = list(items)
        bar = self._scroll.verticalScrollBar()
        pos = bar.value()   # 重建列表后恢复滚动位置
        while self._body.count():
            it = self._body.takeAt(0)
            if w := it.widget():
                w.deleteLater()

        if not self._items:
            hint = QLabel("暂无兑换码数据\n\n请检查数据源，或等待自动更新")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet("color:#7E93A9;font-size:12px;background:transparent;")
            self._body.addWidget(hint)
        else:
            groups: dict[str, list[CodeItem]] = {}
            for it in sorted(self._items, key=lambda i: (i.is_expired, i.is_redeemed)):
                groups.setdefault(it.game_id, []).append(it)
            ordered = ([g for g in GAME_ORDER if g in groups]
                       + [g for g in groups if g not in GAME_ORDER])
            for gid in ordered:
                self._body.addWidget(
                    GameSection(gid, groups[gid], self._open_state,
                                self.markRequested.emit))
            self._body.addStretch(1)
        bar.setValue(pos)


class GameSection(QWidget):
    """单游戏分组：可点击标题栏折叠/展开其码列表。"""

    def __init__(self, game_id: str, rows: list[CodeItem],
                 open_state: dict[str, bool], mark_cb):
        super().__init__()
        self._game_id = game_id
        self._open_state = open_state
        self._mark_cb = mark_cb
        opened = open_state.setdefault(game_id, True)
        color = game_color(game_id)

        head = QWidget()
        head.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 6, 12, 4)
        hl.setSpacing(6)
        arrow = QLabel("▾" if opened else "▸")
        arrow.setStyleSheet(f"color:{color};font-size:12px;background:transparent;")
        self._arrow = arrow
        name = QLabel(rows[0].game_name if rows else game_id)
        name.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:700;background:transparent;")
        alive = sum(1 for r in rows if not r.is_expired)
        count = QLabel(f"{alive}/{len(rows)} 可用")
        count.setStyleSheet("color:#A8BDD3;font-size:11px;background:transparent;")
        hl.addWidget(arrow)
        hl.addWidget(name)
        hl.addStretch(1)
        hl.addWidget(count)
        head.mousePressEvent = lambda e: self._toggle()   # 点击标题折叠

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        for row in rows:
            bl.addWidget(CodeRow(row, mark_cb))
        self._body.setVisible(opened)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(head)
        lay.addWidget(self._body)

    def _toggle(self) -> None:
        opened = not self._open_state[self._game_id]
        self._open_state[self._game_id] = opened
        self._arrow.setText("▾" if opened else "▸")
        self._body.setVisible(opened)


class CodeRow(QWidget):
    """单条兑换码行：徽章 + 码/描述 + 复制按钮 + 状态标签；右键标记菜单。"""

    def __init__(self, item: CodeItem, mark_cb):
        super().__init__()
        self._item = item
        self._mark_cb = mark_cb
        self.setStyleSheet(
            "CodeRow{border-radius:8px;}"
            "CodeRow:hover{background:rgba(62,86,116,110);}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)

        badge = QLabel(item.game_name)
        badge.setStyleSheet(badge_qss(item.game_id))
        badge.setFixedHeight(22)
        self._badge_w = (QFontMetrics(badge.font()).horizontalAdvance(item.game_name)
                         + 16 + 2)   # 文本 + 左右 padding + 描边

        code_style = ("font-family:'Consolas','Microsoft YaHei';font-size:14px;"
                      "font-weight:700;background:transparent;")
        if item.is_expired:
            code_style += "color:#98A6B8;text-decoration:line-through;"
        else:
            code_style += "color:#EAF4FB;"
        code_label = QLabel(item.code)
        code_label.setStyleSheet(code_style)
        meta_bits = [b for b in (
            item.rewards, item.source,
            f"有效期至 {item.expires_at}" if item.expires_at else "") if b]
        self._meta_text = " · ".join(meta_bits) or " "
        meta = QLabel(self._meta_text)
        meta.setWordWrap(True)          # 否则长描述撑爆行宽，把徽章挤出面板
        meta.setMaximumWidth(META_MAX_WIDTH)
        meta.setStyleSheet("color:#A8BDD3;font-size:11px;background:transparent;")
        self._meta = meta

        mid = QWidget()
        mid.setStyleSheet("background:transparent;")
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(1)
        ml.addWidget(code_label)
        ml.addWidget(meta)
        self._mid = mid

        copy_btn = QPushButton("复制")
        copy_btn.setFixedSize(58, 24)
        copy_btn.setStyleSheet(BTN_QSS)
        copy_btn.clicked.connect(lambda: self._copy(copy_btn))

        lay.addWidget(badge)
        lay.addWidget(mid, 1)
        lay.addWidget(copy_btn)

        tag_text = ("已过期" if item.is_expired
                    else "已兑换" if item.is_redeemed else "")
        self._tag_w = 0
        if tag_text:
            tag = QLabel(tag_text)
            tag.setStyleSheet(
                ("color:#7E8B9C;border:1px solid #55677D;" if item.is_expired
                 else "color:#7BD8A5;border:1px solid #3F7A5C;")
                + "border-radius:6px;padding:1px 6px;font-size:11px;background:transparent;")
            tag.setFixedHeight(20)
            lay.addWidget(tag)
            self._tag_w = QFontMetrics(tag.font()).horizontalAdvance(tag_text) + 16

    def resizeEvent(self, e) -> None:
        """按当前行宽自适应：重设描述换行宽度，并按实算行数给 mid 设最小高度，
        防止嵌套布局按单行计高导致文字上下截断。"""
        avail = max(110, self.width() - 24 - self._badge_w - self._tag_w - 58 - 34)
        self._meta.setMaximumWidth(avail)
        fm = QFontMetrics(self._meta.font())
        lines = max(1, math.ceil(fm.horizontalAdvance(self._meta_text) / avail))
        self._meta.setFixedHeight(lines * META_LINE_HEIGHT)
        self._mid.setMinimumHeight(CODE_HEIGHT + 2 + lines * META_LINE_HEIGHT)

    def _copy(self, btn: QPushButton) -> None:
        QApplication.clipboard().setText(self._item.code)
        btn.setText("已复制✓")
        btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(800, lambda: (btn.setText("复制"), btn.setEnabled(True)))

    def contextMenuEvent(self, e) -> None:
        it = self._item
        menu = QMenu(self)
        if it.user_status != STATUS_REDEEMED:
            menu.addAction("标记为已兑换",
                           lambda: self._mark_cb(it.uid, STATUS_REDEEMED))
        if not it.is_expired:
            menu.addAction("标记为已过期",
                           lambda: self._mark_cb(it.uid, STATUS_EXPIRED_LOCAL))
        if it.user_status != STATUS_NONE:
            menu.addAction("清除标记", lambda: self._mark_cb(it.uid, None))
        menu.exec(e.globalPos())

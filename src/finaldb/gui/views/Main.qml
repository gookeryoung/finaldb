import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

ApplicationWindow {
    id: root
    visible: true
    width: 1080
    height: 680
    minimumWidth: 880
    minimumHeight: 560
    title: "finaldb"

    // 类型化访问 context property，消除 setContextProperty 导致的 TypeError
    property ThemeController theme: Theme

    // 全局字体绑定到 ThemeController：
    // QGuiApplication.setFont() 仅设置默认值，不会主动刷新已存在的 QML 控件。
    // 在 ApplicationWindow 显式绑定 font 属性，所有未显式设置 font 的
    // 子控件通过 Qt 字体传播机制继承。
    font.family: theme.fontFamily
    font.pixelSize: theme.fontSizeBody
    font.bold: theme.fontBold

    // ========== 全局 palette：未显式设置颜色的控件通过 palette 继承主题色，
    // 避免暗色模式下黑字看不清 ==========
    palette.window: theme.colorBgApp
    palette.windowText: theme.colorTextPrimary
    palette.base: theme.colorBgApp
    palette.alternateBase: theme.colorBgCard
    palette.text: theme.colorTextPrimary
    palette.buttonText: theme.colorTextPrimary
    palette.button: theme.colorBgCard
    palette.highlight: theme.colorPrimary
    palette.highlightedText: theme.colorTextOnPrimary
    palette.mid: theme.colorBorder
    palette.dark: theme.colorSidebarDark
    palette.light: theme.colorBgHover

    // ========== 背景色随主题切换 ==========
    background: Rectangle {
        color: theme.colorBgApp
        Behavior on color { ColorAnimation { duration: 200 } }
    }

    // ========== 主布局：侧边栏 + 内容 ==========
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---------- 左侧侧边栏 ----------
        Sidebar {
            id: sidebar
            Layout.preferredWidth: sidebar.collapsed ? 0 : theme.sidebarWidth
            Layout.fillHeight: true
            // 折叠/展开宽度动画
            Behavior on Layout.preferredWidth {
                NumberAnimation { duration: 200; easing.type: Easing.OutQuad }
            }
        }

        // ---------- 右侧主内容 ----------
        ContentArea {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sidebarRef: sidebar
        }
    }

    // ========== 全局快捷键：Ctrl+1-7 切换页面 ==========
    Shortcut {
        sequence: "Ctrl+1"
        onActivated: sidebar.currentPage = "home"
    }
    Shortcut {
        sequence: "Ctrl+2"
        onActivated: sidebar.currentPage = "clean"
    }
    Shortcut {
        sequence: "Ctrl+3"
        onActivated: sidebar.currentPage = "merge"
    }
    Shortcut {
        sequence: "Ctrl+4"
        onActivated: sidebar.currentPage = "history"
    }
    Shortcut {
        sequence: "Ctrl+5"
        onActivated: sidebar.currentPage = "stats"
    }
    Shortcut {
        sequence: "Ctrl+6"
        onActivated: sidebar.currentPage = "settings"
    }
    Shortcut {
        sequence: "Ctrl+7"
        onActivated: sidebar.currentPage = "about"
    }

    // Ctrl+B：折叠/展开侧边栏
    Shortcut {
        sequence: "Ctrl+B"
        onActivated: sidebar.collapsed = !sidebar.collapsed
    }
}

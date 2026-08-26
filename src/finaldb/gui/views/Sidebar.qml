import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

Pane {
    id: sidebar
    objectName: "sidebar"
    property ThemeController theme: Theme
    padding: 0

    // 侧栏背景：暗色模式深蓝黑，浅色模式纯白
    background: Rectangle {
        objectName: "sidebarBackground"
        color: theme.isDark ? theme.colorSidebarDark : theme.colorBgCard
        Behavior on color { ColorAnimation { duration: 200 } }
    }

    // 右侧 1px 分割线
    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: theme.colorBorder
    }

    // ========== 当前选中页（供 ContentArea 读取） ==========
    property string currentPage: "home"

    // ========== 侧边栏折叠状态（Ctrl+B 切换） ==========
    property bool collapsed: false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // ---------- Logo 区 ----------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            Layout.leftMargin: 20
            Layout.rightMargin: 16

            RowLayout {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Rectangle {
                    width: 28; height: 28; radius: 6
                    color: theme.colorPrimary
                    Label {
                        anchors.centerIn: parent
                        text: "F"
                        color: theme.colorTextOnPrimary
                        font.pixelSize: 14
                        font.bold: true
                    }
                }
                Label {
                    text: "finaldb"
                    font.pixelSize: 15
                    font.bold: true
                    color: theme.colorTextPrimary
                }
            }
        }

        // ---------- 顶部主导航 ----------
        NavItem {
            badge: "源"; label: "数据源"; pageId: "home"
            selected: sidebar.currentPage === "home"
            onClicked: sidebar.currentPage = "home"
        }
        NavItem {
            badge: "整"; label: "数据整理"; pageId: "clean"
            selected: sidebar.currentPage === "clean"
            onClicked: sidebar.currentPage = "clean"
        }
        NavItem {
            badge: "合"; label: "合并去重"; pageId: "merge"
            selected: sidebar.currentPage === "merge"
            onClicked: sidebar.currentPage = "merge"
        }
        NavItem {
            badge: "版"; label: "版本历史"; pageId: "history"
            selected: sidebar.currentPage === "history"
            onClicked: sidebar.currentPage = "history"
        }

        Item { Layout.fillHeight: true }  // 弹性撑开

        // ---------- 底部辅助导航 ----------
        NavItem {
            badge: "统"; label: "统计"; pageId: "stats"
            selected: sidebar.currentPage === "stats"
            onClicked: sidebar.currentPage = "stats"
        }
        NavItem {
            badge: "设"; label: "设置"; pageId: "settings"
            selected: sidebar.currentPage === "settings"
            onClicked: sidebar.currentPage = "settings"
        }
        NavItem {
            badge: "关"; label: "关于"; pageId: "about"
            selected: sidebar.currentPage === "about"
            onClicked: sidebar.currentPage = "about"
        }

        // ---------- 暗色切换 ----------
        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 14
            Layout.rightMargin: 14
            Layout.topMargin: 8
            Layout.bottomMargin: 16
            Layout.preferredHeight: 36
            radius: 8
            color: theme.isDark ? theme.colorBgHover : theme.colorBgApp
            border.color: theme.colorBorder
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                // 月相符号做暗色模式图标（P1 无 SVG 资产，后续迭代引入）
                Label {
                    text: "◐"
                    font.pixelSize: 14
                    color: theme.colorTextSecondary
                }
                Label {
                    text: "暗色模式"
                    font.pixelSize: 12
                    color: theme.colorTextSecondary
                    Layout.fillWidth: true
                }
                // 自定义开关
                Rectangle {
                    width: 36; height: 20; radius: 10
                    color: theme.isDark ? theme.colorPrimary : theme.colorBorder
                    Behavior on color { ColorAnimation { duration: 150 } }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: theme.setDark(!theme.isDark)
                    }
                    Rectangle {
                        width: 16; height: 16; radius: 8
                        color: "#FFFFFF"
                        x: theme.isDark ? 18 : 2
                        anchors.verticalCenter: parent.verticalCenter
                        Behavior on x { NumberAnimation { duration: 150 } }
                    }
                }
            }
        }
    }
}

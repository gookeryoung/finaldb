import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 侧边栏导航项：字母色块图标 + 文本，选中态左侧强调竖条
Pane {
    id: navItem
    property ThemeController theme: Theme
    padding: 0

    // 导航项属性：字母图标 / 文本 / 页面 id / 选中态
    property string badge: ""
    property string label: ""
    property string pageId: ""
    property bool selected: false
    signal clicked()

    implicitHeight: 40
    background: Rectangle {
        color: navItem.selected
               ? (theme.isDark ? theme.colorBgSelected : theme.colorBgSelected)
               : (navMouseArea.containsMouse ? theme.colorBgHover : "transparent")
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    // 选中态左侧 3px 强调竖条
    Rectangle {
        visible: navItem.selected
        anchors.left: parent.left
        width: 3
        height: parent.height
        color: theme.colorPrimary
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 12
        spacing: 10

        // 字母色块图标（P1 无 SVG 资产，用色块代替）
        Rectangle {
            width: 22; height: 22; radius: 5
            color: navItem.selected ? theme.colorPrimary
                                    : (theme.isDark ? theme.colorBgSelected : theme.colorBgSelected)
            Label {
                anchors.centerIn: parent
                text: navItem.badge
                color: navItem.selected ? theme.colorTextOnPrimary : theme.colorTextSecondary
                font.pixelSize: 11
                font.bold: true
            }
        }

        Label {
            text: navItem.label
            font.pixelSize: theme.fontSizeBody
            color: navItem.selected ? theme.colorTextPrimary : theme.colorTextSecondary
            Layout.fillWidth: true
        }
    }

    MouseArea {
        id: navMouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: navItem.clicked()
    }
}

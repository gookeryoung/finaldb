import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 页面占位组件：页面标题 + 说明（各页面 P2 起逐个替换为真实实现）
Pane {
    id: page
    property ThemeController theme: Theme
    padding: 0

    // 页面属性：标题 / 说明文字 / 副标题徽标字母
    property string pageTitle: ""
    property string description: ""
    property string badge: ""

    background: Rectangle {
        color: theme.colorBgCard
        radius: theme.radiusMd
        border.color: theme.colorBorder
        border.width: 1
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: theme.spacingSm

        // 标题行：徽标色块 + 标题
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: theme.spacingSm
            Rectangle {
                width: 40; height: 40; radius: theme.radiusMd
                color: theme.colorPrimary
                Label {
                    anchors.centerIn: parent
                    text: page.badge
                    color: theme.colorTextOnPrimary
                    font.pixelSize: 18
                    font.bold: true
                }
            }
            Label {
                text: page.pageTitle
                font.pixelSize: theme.fontSizePageTitle
                font.bold: true
                color: theme.colorTextPrimary
            }
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: page.description
            font.pixelSize: theme.fontSizeBody
            color: theme.colorTextSecondary
        }
    }
}

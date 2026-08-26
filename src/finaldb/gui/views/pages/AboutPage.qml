import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 关于页：版本信息与开源许可
Pane {
    id: page
    objectName: "aboutPage"
    property ThemeController theme: Theme
    padding: 0

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 标题 ----------
        Label {
            text: "关于"
            font.pixelSize: theme.fontSizePageTitle
            font.bold: true
            color: theme.colorTextPrimary
        }

        // ---------- 产品信息 ----------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 152
            color: theme.colorBgCard
            radius: theme.radiusMd
            border.color: theme.colorBorder
            border.width: 1

            ColumnLayout {
                anchors.centerIn: parent
                spacing: theme.spacingSm

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: theme.spacingSm

                    Rectangle {
                        width: 48; height: 48; radius: theme.radiusMd
                        color: theme.colorPrimary
                        Label {
                            anchors.centerIn: parent
                            text: "库"
                            color: theme.colorTextOnPrimary
                            font.pixelSize: 22
                            font.bold: true
                        }
                    }
                    Label {
                        text: "finaldb"
                        font.pixelSize: theme.fontSizeTitle
                        font.bold: true
                        color: theme.colorTextPrimary
                    }
                    Label {
                        text: "v" + AboutCtrl.version
                        font.pixelSize: theme.fontSizeBody
                        color: theme.colorTextSecondary
                    }
                }
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "终极数据库管理软件：导入、整理、合并去重与快照级版本控制"
                    font.pixelSize: theme.fontSizeBody
                    color: theme.colorTextSecondary
                }
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "开源许可: " + AboutCtrl.licenseText
                    font.pixelSize: theme.fontSizeCaption
                    color: theme.colorTextSecondary
                }
            }
        }

        // ---------- 运行环境 ----------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: theme.colorBgCard
            radius: theme.radiusMd
            border.color: theme.colorBorder
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: theme.spacingSm

                Label {
                    text: "运行环境"
                    font.pixelSize: theme.fontSizeHeading
                    font.bold: true
                    color: theme.colorTextPrimary
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: theme.spacingMd
                    rowSpacing: theme.spacingSm

                    Label { text: "Python"; color: theme.colorTextSecondary; font.pixelSize: theme.fontSizeBody }
                    Label { text: AboutCtrl.pythonVersion; color: theme.colorTextPrimary; font.pixelSize: theme.fontSizeBody }
                    Label { text: "Qt"; color: theme.colorTextSecondary; font.pixelSize: theme.fontSizeBody }
                    Label { text: AboutCtrl.qtVersion; color: theme.colorTextPrimary; font.pixelSize: theme.fontSizeBody }
                    Label { text: "PySide2"; color: theme.colorTextSecondary; font.pixelSize: theme.fontSizeBody }
                    Label { text: AboutCtrl.pyside2Version; color: theme.colorTextPrimary; font.pixelSize: theme.fontSizeBody }
                    Label { text: "dulwich"; color: theme.colorTextSecondary; font.pixelSize: theme.fontSizeBody }
                    Label { text: AboutCtrl.dulwichVersion; color: theme.colorTextPrimary; font.pixelSize: theme.fontSizeBody }
                }

                Item { Layout.fillHeight: true }

                Label {
                    text: "界面与引擎均为离线运行，数据存储于本地工作区，不上传任何远端。"
                    font.pixelSize: theme.fontSizeCaption
                    color: theme.colorTextSecondary
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}

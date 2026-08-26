import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 设置页：外观（暗色模式/字号）与数据（工作区根目录）偏好
Pane {
    id: page
    objectName: "settingsPage"
    property ThemeController theme: Theme
    padding: 0

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 顶部标题 ----------
        Label {
            text: "设置"
            font.pixelSize: theme.fontSizePageTitle
            font.bold: true
            color: theme.colorTextPrimary
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: settingsColumn.implicitHeight
            clip: true

            ColumnLayout {
                id: settingsColumn
                width: parent.width
                spacing: theme.spacingMd

                // ---------- 外观 ----------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 132
                    color: theme.colorBgCard
                    radius: theme.radiusMd
                    border.color: theme.colorBorder
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: theme.spacingSm

                        Label {
                            text: "外观"
                            font.pixelSize: theme.fontSizeHeading
                            font.bold: true
                            color: theme.colorTextPrimary
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: "暗色模式"
                                font.pixelSize: theme.fontSizeBody
                                color: theme.colorTextPrimary
                                Layout.fillWidth: true
                            }
                            Switch {
                                objectName: "darkSwitch"
                                checked: Theme.isDark
                                onToggled: Theme.setDark(checked)
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: "界面字号"
                                font.pixelSize: theme.fontSizeBody
                                color: theme.colorTextPrimary
                            }
                            Label {
                                text: theme.fontSizeBody + " px"
                                font.pixelSize: theme.fontSizeCaption
                                color: theme.colorTextSecondary
                            }
                            Slider {
                                objectName: "fontSlider"
                                Layout.fillWidth: true
                                from: 12
                                to: 20
                                stepSize: 1
                                snapMode: Slider.SnapAlways
                                value: theme.fontSizeBody
                                onMoved: Theme.setBaseFontSize(value)
                            }
                        }
                    }
                }

                // ---------- 数据 ----------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 96
                    color: theme.colorBgCard
                    radius: theme.radiusMd
                    border.color: theme.colorBorder
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: theme.spacingSm

                        Label {
                            text: "数据"
                            font.pixelSize: theme.fontSizeHeading
                            font.bold: true
                            color: theme.colorTextPrimary
                        }
                        Label {
                            text: "工作区根目录: " + WorkspaceCtrl.workspaceRoot
                            font.pixelSize: theme.fontSizeBody
                            color: theme.colorTextSecondary
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                        }
                    }
                }

                // ---------- 版本 ----------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: theme.colorBgCard
                    radius: theme.radiusMd
                    border.color: theme.colorBorder
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: theme.spacingSm

                        Label {
                            text: "版本"
                            font.pixelSize: theme.fontSizeHeading
                            font.bold: true
                            color: theme.colorTextPrimary
                        }
                        Label {
                            text: "finaldb " + AboutCtrl.version + "，详细依赖清单见「关于」页"
                            font.pixelSize: theme.fontSizeBody
                            color: theme.colorTextSecondary
                        }
                    }
                }
            }
        }
    }
}

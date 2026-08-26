import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 统计页：工作区表分布概览与条形图
Pane {
    id: page
    objectName: "statsPage"
    property ThemeController theme: Theme
    padding: 0

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 顶部工具栏 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingSm

            Label {
                text: "统计"
                font.pixelSize: theme.fontSizePageTitle
                font.bold: true
                color: theme.colorTextPrimary
            }
            Label {
                text: WorkspaceCtrl.currentWorkspace
                      ? "当前工作区: " + WorkspaceCtrl.currentWorkspace
                      : "未选择工作区（请先在数据源页选择）"
                font.pixelSize: theme.fontSizeCaption
                color: theme.colorTextSecondary
                Layout.fillWidth: true
                elide: Text.ElideMiddle
            }

            Button {
                text: "刷新"
                onClicked: StatsCtrl.load_stats(WorkspaceCtrl.currentWorkspacePath)
            }
        }

        // ---------- 摘要 ----------
        Label {
            objectName: "statsSummary"
            text: StatsCtrl.summaryText
            font.pixelSize: theme.fontSizeBody
            color: theme.colorTextPrimary
            Layout.fillWidth: true
        }

        // ---------- 表分布条形图 ----------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: theme.colorBgCard
            radius: theme.radiusMd
            border.color: theme.colorBorder
            border.width: 1

            Flickable {
                anchors.fill: parent
                anchors.margins: 12
                contentHeight: barColumn.implicitHeight
                clip: true

                ColumnLayout {
                    id: barColumn
                    width: parent.width
                    spacing: theme.spacingSm

                    Repeater {
                        model: StatsCtrl.statsModel

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spacingSm

                            Label {
                                text: model.name
                                font.pixelSize: theme.fontSizeSmall
                                color: theme.colorTextPrimary
                                Layout.preferredWidth: 140
                                elide: Text.ElideMiddle
                            }
                            // 条形：宽度按行数占比（0.0~1.0）
                            Rectangle {
                                Layout.preferredWidth: Math.max(4, model.ratio * (barColumn.width - 240))
                                Layout.preferredHeight: 14
                                radius: theme.radiusSm
                                color: theme.colorPrimary
                            }
                            Label {
                                text: model.rows + " 行"
                                font.pixelSize: theme.fontSizeCaption
                                color: theme.colorTextSecondary
                            }
                        }
                    }
                }
            }
        }
    }

    // 工作区切换后自动重载统计
    Connections {
        target: WorkspaceCtrl
        onCurrent_changed: StatsCtrl.load_stats(WorkspaceCtrl.currentWorkspacePath)
    }

    // 首次进入页面时加载
    Component.onCompleted: StatsCtrl.load_stats(WorkspaceCtrl.currentWorkspacePath)
}

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 数据整理页：表/列选择 + 清洗规则配置 + 预览与统计 + 应用到新表
Pane {
    id: page
    objectName: "cleanPage"
    property ThemeController theme: Theme
    padding: 0

    // 当前选择的表名（QML 侧状态，槽调用显式传参）
    property string currentTable: ""
    property string currentColumn: ""

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 顶部工具栏 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingSm

            Label {
                text: "数据整理"
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

            BusyIndicator {
                visible: CleanCtrl.busy
                running: CleanCtrl.busy
                implicitWidth: 22
                implicitHeight: 22
            }

            Button {
                text: "预览效果"
                highlighted: true
                enabled: page.currentTable !== "" && ruleList.count > 0 && !CleanCtrl.busy
                onClicked: CleanCtrl.preview(WorkspaceCtrl.currentWorkspacePath, page.currentTable)
            }
            Button {
                text: "应用到新表"
                enabled: page.currentTable !== "" && ruleList.count > 0 && !CleanCtrl.busy
                onClicked: CleanCtrl.apply(WorkspaceCtrl.currentWorkspacePath, page.currentTable, targetField.text)
            }
        }

        // ---------- 主体两栏：规则配置 | 预览 ----------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.spacingMd

            // 左：规则配置面板
            Rectangle {
                Layout.preferredWidth: 380
                Layout.fillHeight: true
                color: theme.colorBgCard
                radius: theme.radiusMd
                border.color: theme.colorBorder
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: theme.spacingSm

                    // 表选择
                    Label {
                        text: "数据表"
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                    }
                    ComboBox {
                        id: tableCombo
                        Layout.fillWidth: true
                        model: CleanCtrl.tablesModel
                        textRole: "name"
                        displayText: page.currentTable ? page.currentTable : "选择数据表"
                        onActivated: {
                            page.currentTable = tableCombo.textAt(index)
                            page.currentColumn = ""
                            CleanCtrl.load_columns(WorkspaceCtrl.currentWorkspacePath, page.currentTable)
                        }
                        // 工作区切换时重置选择并重载表列表
                        Connections {
                            target: WorkspaceCtrl
                            onCurrent_changed: {
                                page.currentTable = ""
                                page.currentColumn = ""
                                CleanCtrl.load_tables(WorkspaceCtrl.currentWorkspacePath)
                            }
                        }
                    }

                    // 规则类型
                    Label {
                        text: "清洗规则"
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                    }
                    ComboBox {
                        id: kindCombo
                        Layout.fillWidth: true
                        model: ["去首尾空白", "转大写", "转小写", "文本替换", "文本转数值", "缺失值填充", "删除缺失行"]
                        property var kindValues: ["trim", "case", "case", "replace", "to_number", "fill_missing", "drop_missing"]
                    }

                    // 目标列
                    Label {
                        text: "目标列"
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                    }
                    ComboBox {
                        id: columnCombo
                        Layout.fillWidth: true
                        model: CleanCtrl.columnsModel
                        textRole: "text"
                        displayText: page.currentColumn ? page.currentColumn : "选择目标列"
                        onActivated: page.currentColumn = columnCombo.textAt(index)
                    }

                    // 参数区（按规则类型显隐）
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacingSm
                        visible: kindCombo.currentIndex === 3 || kindCombo.currentIndex === 5

                        Label {
                            text: kindCombo.currentIndex === 5 ? "填充值" : "查找"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        TextField {
                            id: valueField
                            Layout.fillWidth: true
                            placeholderText: "必填"
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacingSm
                        visible: kindCombo.currentIndex === 3

                        Label {
                            text: "替换为"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        TextField {
                            id: replacementField
                            Layout.fillWidth: true
                            placeholderText: "替换文本（可为空）"
                        }
                    }

                    Button {
                        text: "添加规则"
                        Layout.fillWidth: true
                        onClicked: {
                            CleanCtrl.add_rule(
                                kindCombo.kindValues[kindCombo.currentIndex],
                                page.currentColumn,
                                valueField.text,
                                replacementField.text,
                                kindCombo.kindValues[kindCombo.currentIndex] === "case"
                                    ? (kindCombo.currentIndex === 1 ? "upper" : "lower")
                                    : ""
                            )
                        }
                    }

                    // 已配置规则列表
                    Label {
                        text: "已配置规则（按顺序应用）"
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                        Layout.topMargin: theme.spacingSm
                    }
                    ListView {
                        id: ruleList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: CleanCtrl.rulesModel
                        spacing: 2

                        delegate: Rectangle {
                            width: ruleList.width - 4
                            height: 36
                            x: 2
                            radius: theme.radiusSm
                            color: theme.isDark ? "#22232E" : "#FAFBFC"
                            border.color: theme.colorBorder
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 6
                                spacing: 6

                                Label {
                                    text: model.display
                                    font.pixelSize: theme.fontSizeSmall
                                    color: theme.colorTextPrimary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Label {
                                    text: "移除"
                                    font.pixelSize: theme.fontSizeCaption
                                    color: rmMouse.containsMouse ? theme.colorDanger : theme.colorTextSecondary
                                    MouseArea {
                                        id: rmMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: CleanCtrl.remove_rule(index)
                                    }
                                }
                            }
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: ruleList.count === 0
                            text: "暂无规则\n在上方配置并点击「添加规则」"
                            horizontalAlignment: Text.AlignHCenter
                            color: theme.colorTextSecondary
                            font.pixelSize: theme.fontSizeSmall
                        }
                    }

                    Button {
                        text: "清空规则"
                        Layout.fillWidth: true
                        onClicked: CleanCtrl.clear_rules()
                    }
                }
            }

            // 右：预览与统计
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: theme.colorBgCard
                radius: theme.radiusMd
                border.color: theme.colorBorder
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: theme.spacingSm

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacingSm

                        Label {
                            text: page.currentTable ? "清洗预览: " + page.currentTable : "清洗预览"
                            font.pixelSize: theme.fontSizeHeading
                            font.bold: true
                            color: theme.colorTextPrimary
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                        }

                        // 新表名输入
                        Label {
                            text: "新表名"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                            visible: page.currentTable !== ""
                        }
                        TextField {
                            id: targetField
                            visible: page.currentTable !== ""
                            placeholderText: "默认 " + (page.currentTable ? page.currentTable + "_clean" : "")
                            implicitWidth: 160
                        }
                    }

                    // 统计报告
                    Label {
                        Layout.fillWidth: true
                        visible: CleanCtrl.reportText !== ""
                        text: CleanCtrl.reportText
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                        wrapMode: Text.WordWrap
                    }

                    TableView {
                        id: previewTable
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columnWidthProvider: function (column) { return Math.max(110, width / Math.max(1, model ? model.columnCount : 1)) }
                        clip: true
                        model: CleanCtrl.previewModel
                        visible: previewTable.rows > 0

                        delegate: Rectangle {
                            implicitWidth: 110
                            implicitHeight: 30
                            color: row % 2 === 0 ? "transparent" : (theme.isDark ? "#22232E" : "#FAFBFC")
                            border.color: theme.colorBorder
                            border.width: 1

                            Label {
                                anchors.fill: parent
                                anchors.margins: 6
                                verticalAlignment: Text.AlignVCenter
                                text: model.display === undefined ? "" : String(model.display)
                                font.pixelSize: theme.fontSizeSmall
                                color: theme.colorTextPrimary
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Label {
                        visible: previewTable.rows === 0
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: page.currentTable ? "点击「预览效果」查看清洗后的前 200 行" : "选择数据表后配置规则"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: theme.colorTextSecondary
                        font.pixelSize: theme.fontSizeBody
                    }
                }
            }
        }
    }

    // 控制器信号 → 顶部状态浮层
    Connections {
        target: CleanCtrl
        onApplied: statusToast.show(message, false)
        onFailed: statusToast.show(message, true)
        onError_raised: statusToast.show(message, true)
    }

    // 状态浮层
    Rectangle {
        id: statusToast
        function show(message, isError) {
            toastText.text = message
            statusToast.color = isError ? theme.colorDanger : theme.colorSuccess
            statusToast.visible = true
            toastTimer.restart()
        }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 8
        width: Math.min(page.width - 48, toastText.implicitWidth + 32)
        height: 34
        radius: theme.radiusSm
        visible: false
        color: theme.colorSuccess

        Label {
            id: toastText
            anchors.centerIn: parent
            color: "#FFFFFF"
            font.pixelSize: theme.fontSizeSmall
            elide: Text.ElideMiddle
            width: parent.width - 32
            horizontalAlignment: Text.AlignHCenter
        }

        Timer {
            id: toastTimer
            interval: 3200
            onTriggered: statusToast.visible = false
        }
    }
}

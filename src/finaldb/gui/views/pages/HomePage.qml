import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3 as Dialogs
import FinalDB.Theme 1.0

// 数据源页：工作区管理 + 数据导入 + 表预览
Pane {
    id: page
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
                text: "数据源"
                font.pixelSize: theme.fontSizePageTitle
                font.bold: true
                color: theme.colorTextPrimary
            }
            Label {
                text: WorkspaceCtrl.currentWorkspace
                      ? "当前工作区: " + WorkspaceCtrl.currentWorkspace
                      : "未选择工作区"
                font.pixelSize: theme.fontSizeCaption
                color: theme.colorTextSecondary
                Layout.fillWidth: true
                elide: Text.ElideMiddle
            }

            BusyIndicator {
                visible: WorkspaceCtrl.busy
                running: WorkspaceCtrl.busy
                implicitWidth: 22
                implicitHeight: 22
            }

            Button {
                text: "新建工作区"
                highlighted: true
                onClicked: newWorkspaceDialog.open()
            }
            Button {
                text: "导入数据"
                enabled: WorkspaceCtrl.currentWorkspace !== "" && !WorkspaceCtrl.busy
                onClicked: importDialog.open()
            }
        }

        // ---------- 主体三栏：工作区列表 | 表列表 | 预览 ----------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.spacingMd

            // 工作区卡片列表
            Rectangle {
                Layout.preferredWidth: 240
                Layout.fillHeight: true
                color: theme.colorBgCard
                radius: theme.radiusMd
                border.color: theme.colorBorder
                border.width: 1

                ListView {
                    id: wsList
                    anchors.fill: parent
                    anchors.margins: 1
                    clip: true
                    model: WorkspaceCtrl.model
                    spacing: 2

                    delegate: Rectangle {
                        width: wsList.width - 8
                        height: 72
                        x: 4
                        radius: theme.radiusSm
                        color: model.name === WorkspaceCtrl.currentWorkspace
                               ? theme.colorBgSelected
                               : (mouse.containsMouse ? theme.colorBgHover : "transparent")

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Label {
                                    text: model.name
                                    font.pixelSize: theme.fontSizeBody
                                    font.bold: true
                                    color: theme.colorTextPrimary
                                    Layout.fillWidth: true
                                    elide: Text.ElideMiddle
                                }
                                // 删除按钮（低频操作收进卡片）
                                Label {
                                    text: "✕"
                                    font.pixelSize: theme.fontSizeCaption
                                    color: mouse2.containsMouse ? theme.colorDanger : theme.colorTextSecondary
                                    MouseArea {
                                        id: mouse2
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: {
                                            deleteConfirm.wsName = model.name
                                            deleteConfirm.open()
                                        }
                                    }
                                }
                            }
                            Label {
                                text: model.tableCount + " 张表 · " + model.totalRows + " 行 · " + model.updatedAt
                                font.pixelSize: theme.fontSizeCaption
                                color: theme.colorTextSecondary
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }

                        MouseArea {
                            id: mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            // 点击选中（不遮挡删除按钮区域）
                            acceptedButtons: Qt.LeftButton
                            onPressed: {
                                WorkspaceCtrl.select_workspace(model.name)
                                PreviewCtrl.clear()
                            }
                        }
                    }

                    // 空态提示
                    Label {
                        anchors.centerIn: parent
                        visible: wsList.count === 0
                        text: "暂无工作区\n点击右上角「新建工作区」开始"
                        horizontalAlignment: Text.AlignHCenter
                        color: theme.colorTextSecondary
                        font.pixelSize: theme.fontSizeBody
                    }
                }
            }

            // 当前工作区表列表
            Rectangle {
                Layout.preferredWidth: 180
                Layout.fillHeight: true
                color: theme.colorBgCard
                radius: theme.radiusMd
                border.color: theme.colorBorder
                border.width: 1

                ListView {
                    id: tableList
                    anchors.fill: parent
                    anchors.margins: 1
                    clip: true
                    model: WorkspaceCtrl.tableModel
                    spacing: 2

                    delegate: Rectangle {
                        width: tableList.width - 8
                        height: 40
                        x: 4
                        radius: theme.radiusSm
                        color: PreviewCtrl.tableName === model.name
                               ? theme.colorBgSelected
                               : (tmouse.containsMouse ? theme.colorBgHover : "transparent")

                        Label {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: Text.AlignVCenter
                            text: model.name + " (" + model.rows + ")"
                            font.pixelSize: theme.fontSizeSmall
                            color: theme.colorTextPrimary
                            elide: Text.ElideMiddle
                        }

                        MouseArea {
                            id: tmouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: PreviewCtrl.load_table(WorkspaceCtrl.currentWorkspacePath, model.name)
                        }
                    }

                    Label {
                        anchors.centerIn: parent
                        visible: tableList.count === 0
                        text: WorkspaceCtrl.currentWorkspace ? "无数据表\n导入数据后显示" : "先选择工作区"
                        horizontalAlignment: Text.AlignHCenter
                        color: theme.colorTextSecondary
                        font.pixelSize: theme.fontSizeSmall
                    }
                }
            }

            // 数据预览面板
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

                    Label {
                        text: PreviewCtrl.tableName ? "预览: " + PreviewCtrl.tableName : "数据预览"
                        font.pixelSize: theme.fontSizeHeading
                        font.bold: true
                        color: theme.colorTextPrimary
                    }

                    TableView {
                        id: previewTable
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columnWidthProvider: function (column) { return Math.max(110, width / Math.max(1, model ? model.columnCount : 1)) }
                        clip: true
                        model: PreviewCtrl.model
                        visible: PreviewCtrl.tableName !== ""

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
                        visible: PreviewCtrl.tableName === ""
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "选择左侧数据表查看前 200 行"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: theme.colorTextSecondary
                        font.pixelSize: theme.fontSizeBody
                    }
                }
            }
        }
    }

    // ---------- 新建工作区对话框 ----------
    Dialog {
        id: newWorkspaceDialog
        title: "新建工作区"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: 320

        ColumnLayout {
            width: parent.width
            spacing: theme.spacingSm
            Label {
                text: "名称（字母/数字/下划线/连字符）"
                font.pixelSize: theme.fontSizeCaption
                color: theme.colorTextSecondary
            }
            TextField {
                id: wsNameField
                placeholderText: "例如 sales_2024"
                Layout.fillWidth: true
            }
        }

        onAccepted: {
            if (wsNameField.text.trim()) {
                WorkspaceCtrl.create_workspace(wsNameField.text.trim())
                wsNameField.text = ""
            }
        }
    }

    // ---------- 删除确认 ----------
    Dialog {
        id: deleteConfirm
        title: "删除工作区"
        modal: true
        standardButtons: Dialog.Yes | Dialog.No
        width: 320
        property string wsName: ""

        Label {
            text: "确认删除工作区「" + deleteConfirm.wsName + "」？\n所有数据将被移除且不可恢复。"
            color: theme.colorTextPrimary
            wrapMode: Text.WordWrap
        }

        onAccepted: WorkspaceCtrl.delete_workspace(deleteConfirm.wsName)
    }

    // ---------- 导入文件选择 ----------
    Dialogs.FileDialog {
        id: importDialog
        title: "选择数据文件"
        nameFilters: [
            "数据文件 (*.csv *.tsv *.xlsx *.xlsm *.json *.ndjson)",
            "所有文件 (*)",
        ]
        onAccepted: WorkspaceCtrl.import_file(file.toString())
    }

    // 控制器信号 → 顶部状态浮层
    Connections {
        target: WorkspaceCtrl
        onImport_finished: statusToast.show(message, false)
        onImport_failed: statusToast.show(message, true)
        onError_raised: statusToast.show(message, true)
    }

    // 状态浮层（导入完成/错误提示）
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

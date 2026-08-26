import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 版本历史页：快照列表 + 提交 + 对比 + 回滚
Pane {
    id: page
    objectName: "historyPage"
    property ThemeController theme: Theme
    padding: 0

    // 选中的两个快照引用（对比用，按点击顺序）
    property string refA: ""
    property string refB: ""
    // 当前待回滚的快照引用
    property string restoreRef: ""

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 顶部工具栏 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingSm

            Label {
                text: "版本历史"
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
                visible: HistoryCtrl.busy
                running: HistoryCtrl.busy
                implicitWidth: 22
                implicitHeight: 22
            }

            Button {
                text: "对比选中"
                enabled: page.refA !== "" && page.refB !== "" && !HistoryCtrl.busy
                onClicked: HistoryCtrl.diff(WorkspaceCtrl.currentWorkspacePath, page.refA, page.refB)
            }
            Button {
                text: "回滚到此"
                enabled: page.restoreRef !== "" && !HistoryCtrl.busy
                onClicked: HistoryCtrl.restore(WorkspaceCtrl.currentWorkspacePath, page.restoreRef)
            }
        }

        // ---------- 主体两栏：快照列表 | 提交与对比 ----------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.spacingMd

            // 左：快照列表（点击选中 A/B，双击设为回滚目标）
            Rectangle {
                Layout.preferredWidth: 420
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
                        text: "快照（点击选两个对比，双击设为回滚目标）"
                        font.pixelSize: theme.fontSizeCaption
                        color: theme.colorTextSecondary
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }

                    ListView {
                        id: snapList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: HistoryCtrl.snapshotsModel
                        spacing: 2

                        delegate: Rectangle {
                            width: snapList.width - 4
                            height: 44
                            x: 2
                            radius: theme.radiusSm
                            color: model.shortId === page.refA || model.shortId === page.refB
                                  ? (theme.isDark ? "#2A3040" : "#EAF2FF")
                                  : (theme.isDark ? "#22232E" : "#FAFBFC")
                            border.color: model.shortId === page.restoreRef
                                  ? theme.colorPrimary
                                  : (model.shortId === page.refA || model.shortId === page.refB ? theme.colorPrimary : theme.colorBorder)
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 6
                                anchors.topMargin: 4
                                anchors.bottomMargin: 4
                                spacing: 0

                                Label {
                                    text: model.message
                                    font.pixelSize: theme.fontSizeSmall
                                    color: theme.colorTextPrimary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Label {
                                    text: model.shortId + "  " + model.time
                                    font.pixelSize: theme.fontSizeCaption
                                    color: theme.colorTextSecondary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: page._pick(model.shortId)
                                onDoubleClicked: {
                                    page.restoreRef = model.shortId
                                    page._pick(model.shortId)
                                }
                            }
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: snapList.count === 0
                            text: "暂无快照\n导入数据后自动创建，或在右侧手动提交"
                            horizontalAlignment: Text.AlignHCenter
                            color: theme.colorTextSecondary
                            font.pixelSize: theme.fontSizeSmall
                        }
                    }
                }
            }

            // 右：手动提交 + diff 结果
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

                    // 手动提交
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacingSm

                        Label {
                            text: "提交说明"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        TextField {
                            id: messageField
                            Layout.fillWidth: true
                            placeholderText: "为当前数据打一个快照"
                            onAccepted: HistoryCtrl.commit(WorkspaceCtrl.currentWorkspacePath, messageField.text)
                        }
                        Button {
                            text: "提交快照"
                            highlighted: true
                            enabled: !HistoryCtrl.busy
                            onClicked: HistoryCtrl.commit(WorkspaceCtrl.currentWorkspacePath, messageField.text)
                        }
                    }

                    // 对比结果
                    Label {
                        text: page.refA && page.refB ? "对比 " + page.refA + " → " + page.refB : "对比结果"
                        font.pixelSize: theme.fontSizeHeading
                        font.bold: true
                        color: theme.colorTextPrimary
                        Layout.topMargin: theme.spacingSm
                    }

                    Flickable {
                        id: diffView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: width
                        contentHeight: diffText.implicitHeight
                        visible: HistoryCtrl.diffText !== ""

                        TextArea {
                            id: diffText
                            width: diffView.width
                            readOnly: true
                            wrapMode: Text.NoWrap
                            text: HistoryCtrl.diffText
                            font.family: "Consolas"
                            font.pixelSize: theme.fontSizeSmall
                            color: theme.colorTextPrimary
                            background: Rectangle {
                                color: "transparent"
                            }
                        }

                        ScrollBar.vertical: ScrollBar {}
                    }

                    Label {
                        visible: HistoryCtrl.diffText === ""
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "在左侧选择两个快照后点击「对比选中」\n查看表级差异（表集合、列与行数）"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: theme.colorTextSecondary
                        font.pixelSize: theme.fontSizeBody
                    }
                }
            }
        }
    }

    // ---------- 状态与动作 ----------

    // 点击选中：A 为空选 A，否则 B 为空选 B，否则滚动更新（A←B，B←新）
    function _pick(ref) {
        if (refA === ref) {
            refA = ""
        } else if (refB === ref) {
            refB = ""
        } else if (refA === "") {
            refA = ref
        } else if (refB === "") {
            refB = ref
        } else {
            refA = refB
            refB = ref
        }
    }

    // 工作区切换：清空选择并重载快照列表
    Connections {
        target: WorkspaceCtrl
        onCurrent_changed: {
            page.refA = ""
            page.refB = ""
            page.restoreRef = ""
            HistoryCtrl.load_history(WorkspaceCtrl.currentWorkspacePath)
        }
    }

    // 页面可见时（首次加载）若已有工作区则加载历史
    onVisibleChanged: {
        if (visible && WorkspaceCtrl.currentWorkspacePath)
            HistoryCtrl.load_history(WorkspaceCtrl.currentWorkspacePath)
    }

    // 控制器信号 → 顶部状态浮层
    Connections {
        target: HistoryCtrl
        onApplied: {
            statusToast.show(message, false)
            HistoryCtrl.load_history(WorkspaceCtrl.currentWorkspacePath)
        }
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

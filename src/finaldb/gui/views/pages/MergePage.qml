import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0

// 合并去重页：纵向合并（union）/ 表去重（dedup）/ 两表连接（join）三模式
Pane {
    id: page
    objectName: "mergePage"
    property ThemeController theme: Theme
    padding: 0

    // 多值分隔符：与控制器侧约定一致（\x1f 单元分隔符）
    readonly property string unitSep: "\x1f"

    // 模式状态：0=纵向合并 1=表去重 2=两表连接
    property int mode: 0

    // 各模式的选中状态
    property var unionTables: []
    property string dedupTable: ""
    property var dedupKeys: []
    property string joinLeft: ""
    property string joinRight: ""
    property string joinLeftKey: ""
    property string joinRightKey: ""

    background: Rectangle { color: "transparent" }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacingMd

        // ---------- 顶部工具栏：模式切换 + 工作区 + 执行按钮 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingSm

            Label {
                text: "合并去重"
                font.pixelSize: theme.fontSizePageTitle
                font.bold: true
                color: theme.colorTextPrimary
            }

            // 模式切换按钮组（比 ComboBox 更直观的平铺切换）
            Row {
                spacing: 4
                Repeater {
                    model: ["纵向合并", "表去重", "两表连接"]
                    delegate: Button {
                        text: modelData
                        flat: page.mode === index
                        highlighted: page.mode === index
                        onClicked: page.mode = index
                    }
                }
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
                visible: MergeCtrl.busy
                running: MergeCtrl.busy
                implicitWidth: 22
                implicitHeight: 22
            }

            Button {
                text: "执行"
                highlighted: true
                enabled: page._canApply() && !MergeCtrl.busy
                onClicked: page._apply()
            }
        }

        // ---------- 主体两栏：配置 | 说明 ----------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.spacingMd

            // 左：当前模式的配置面板
            Rectangle {
                Layout.preferredWidth: 400
                Layout.fillHeight: true
                color: theme.colorBgCard
                radius: theme.radiusMd
                border.color: theme.colorBorder
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: theme.spacingSm

                    // ===== 模式 0：纵向合并（多选表）=====
                    ColumnLayout {
                        visible: page.mode === 0
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: theme.spacingSm

                        Label {
                            text: "选择多个表（按顺序纵向堆叠，列按名称对齐）"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            text: "已选 " + page.unionTables.length + " 个表"
                            font.pixelSize: theme.fontSizeCaption
                            color: page.unionTables.length >= 2 ? theme.colorSuccess : theme.colorTextSecondary
                        }
                        ListView {
                            id: unionList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: MergeCtrl.tablesModel
                            spacing: 2

                            delegate: Rectangle {
                                width: unionList.width - 4
                                height: 34
                                x: 2
                                radius: theme.radiusSm
                                color: page.unionTables.indexOf(model.name) >= 0
                                      ? (theme.isDark ? "#2A3040" : "#EAF2FF")
                                      : (theme.isDark ? "#22232E" : "#FAFBFC")
                                border.color: page.unionTables.indexOf(model.name) >= 0 ? theme.colorPrimary : theme.colorBorder
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 6
                                    spacing: 6

                                    Label {
                                        text: page.unionTables.indexOf(model.name) >= 0 ? "✓" : ""
                                        font.pixelSize: theme.fontSizeSmall
                                        color: theme.colorPrimary
                                    }
                                    Label {
                                        text: model.name
                                        font.pixelSize: theme.fontSizeSmall
                                        color: theme.colorTextPrimary
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        text: model.rows + " 行"
                                        font.pixelSize: theme.fontSizeCaption
                                        color: theme.colorTextSecondary
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: page._toggleUnionTable(model.name)
                                }
                            }

                            Label {
                                anchors.centerIn: parent
                                visible: unionList.count === 0
                                text: "工作区暂无数据表\n请先在数据源页导入"
                                horizontalAlignment: Text.AlignHCenter
                                color: theme.colorTextSecondary
                                font.pixelSize: theme.fontSizeSmall
                            }
                        }
                    }

                    // ===== 模式 1：表去重 =====
                    ColumnLayout {
                        visible: page.mode === 1
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: theme.spacingSm

                        Label {
                            text: "数据表"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        ComboBox {
                            id: dedupTableCombo
                            Layout.fillWidth: true
                            model: MergeCtrl.tablesModel
                            textRole: "name"
                            displayText: page.dedupTable ? page.dedupTable : "选择数据表"
                            onActivated: {
                                page.dedupTable = dedupTableCombo.textAt(index)
                                page.dedupKeys = []
                                MergeCtrl.load_columns(WorkspaceCtrl.currentWorkspacePath, page.dedupTable)
                            }
                        }

                        Label {
                            text: "去重键（不选 = 按整行去重，保留首次出现）"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        ListView {
                            id: dedupKeysList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: MergeCtrl.dedupColumnsModel
                            spacing: 2

                            delegate: Rectangle {
                                width: dedupKeysList.width - 4
                                height: 30
                                x: 2
                                radius: theme.radiusSm
                                color: page.dedupKeys.indexOf(model.display) >= 0
                                      ? (theme.isDark ? "#2A3040" : "#EAF2FF")
                                      : (theme.isDark ? "#22232E" : "#FAFBFC")
                                border.color: page.dedupKeys.indexOf(model.display) >= 0 ? theme.colorPrimary : theme.colorBorder
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 6
                                    spacing: 6

                                    Label {
                                        text: page.dedupKeys.indexOf(model.display) >= 0 ? "✓" : ""
                                        font.pixelSize: theme.fontSizeSmall
                                        color: theme.colorPrimary
                                    }
                                    Label {
                                        text: model.display
                                        font.pixelSize: theme.fontSizeSmall
                                        color: theme.colorTextPrimary
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: page._toggleDedupKey(model.display)
                                }
                            }

                            Label {
                                anchors.centerIn: parent
                                visible: dedupKeysList.count === 0
                                text: page.dedupTable ? "该表无列" : "选择数据表后配置键列"
                                horizontalAlignment: Text.AlignHCenter
                                color: theme.colorTextSecondary
                                font.pixelSize: theme.fontSizeSmall
                            }
                        }
                    }

                    // ===== 模式 2：两表连接 =====
                    ColumnLayout {
                        visible: page.mode === 2
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: theme.spacingSm

                        Label {
                            text: "左表 / 右表"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spacingSm

                            ComboBox {
                                id: leftCombo
                                Layout.fillWidth: true
                                model: MergeCtrl.tablesModel
                                textRole: "name"
                                displayText: page.joinLeft ? page.joinLeft : "左表"
                                onActivated: {
                                    page.joinLeft = leftCombo.textAt(index)
                                    MergeCtrl.load_join_columns(
                                        WorkspaceCtrl.currentWorkspacePath,
                                        page.joinLeft, page.joinRight)
                                }
                            }
                            ComboBox {
                                id: rightCombo
                                Layout.fillWidth: true
                                model: MergeCtrl.tablesModel
                                textRole: "name"
                                displayText: page.joinRight ? page.joinRight : "右表"
                                onActivated: {
                                    page.joinRight = rightCombo.textAt(index)
                                    MergeCtrl.load_join_columns(
                                        WorkspaceCtrl.currentWorkspacePath,
                                        page.joinLeft, page.joinRight)
                                }
                            }
                        }

                        Label {
                            text: "左键列 / 右键列"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spacingSm

                            ComboBox {
                                id: leftKeyCombo
                                Layout.fillWidth: true
                                model: MergeCtrl.leftColumnsModel
                                displayText: page.joinLeftKey ? page.joinLeftKey : "左键列"
                                onActivated: page.joinLeftKey = leftKeyCombo.textAt(index)
                            }
                            ComboBox {
                                id: rightKeyCombo
                                Layout.fillWidth: true
                                model: MergeCtrl.rightColumnsModel
                                displayText: page.joinRightKey ? page.joinRightKey : "右键列"
                                onActivated: page.joinRightKey = rightKeyCombo.textAt(index)
                            }
                        }

                        Label {
                            text: "连接方式"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        Row {
                            spacing: 4
                            Repeater {
                                model: ["内连接（仅匹配行）", "左连接（保留左表全部）"]
                                delegate: Button {
                                    text: modelData
                                    flat: howGroup.currentIndex === index
                                    highlighted: howGroup.currentIndex === index
                                    onClicked: howGroup.currentIndex = index
                                    ButtonGroup.group: howGroup
                                }
                            }
                        }
                        ButtonGroup { id: howGroup }
                    }

                    // 新表名（三模式共用，置底部）
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacingSm

                        Label {
                            text: "新表名"
                            font.pixelSize: theme.fontSizeCaption
                            color: theme.colorTextSecondary
                        }
                        TextField {
                            id: targetField
                            Layout.fillWidth: true
                            placeholderText: "默认自动命名"
                        }
                    }
                }
            }

            // 右：模式说明
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
                        text: ["纵向合并", "表去重", "两表连接"][page.mode]
                        font.pixelSize: theme.fontSizeHeading
                        font.bold: true
                        color: theme.colorTextPrimary
                    }
                    Label {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        wrapMode: Text.WordWrap
                        font.pixelSize: theme.fontSizeBody
                        color: theme.colorTextSecondary
                        verticalAlignment: Text.AlignTop
                        text: page.mode === 0
                              ? "将多个结构相似的表按顺序纵向堆叠为一张新表。\n\n列按名称对齐：首表列序优先，新列追加，缺失补空值。\n至少选择两个表。"
                              : (page.mode === 1
                                 ? "对单表去重并写入新表（原表不动）。\n\n按所选键列组合判重，键相同保留首次出现的行；不选键列则按整行判重。"
                                 : "按左右键列把右表字段拼到左表，写入新表。\n\n内连接只保留匹配行；左连接保留左表全部行，无匹配的右字段补空。右表同名列自动加 _2 后缀，一键多匹配会展开为多行。")
                    }
                }
            }
        }
    }

    // ---------- 状态与动作 ----------

    // 切换纵向合并表选中项（重新赋值数组以触发绑定刷新）
    function _toggleUnionTable(name) {
        var list = unionTables.slice()
        var pos = list.indexOf(name)
        if (pos >= 0)
            list.splice(pos, 1)
        else
            list.push(name)
        unionTables = list
    }

    // 切换去重键列选中项
    function _toggleDedupKey(name) {
        var list = dedupKeys.slice()
        var pos = list.indexOf(name)
        if (pos >= 0)
            list.splice(pos, 1)
        else
            list.push(name)
        dedupKeys = list
    }

    function _canApply() {
        if (!WorkspaceCtrl.currentWorkspace)
            return false
        if (mode === 0)
            return unionTables.length >= 2
        if (mode === 1)
            return dedupTable !== ""
        return joinLeft !== "" && joinRight !== "" && joinLeftKey !== "" && joinRightKey !== ""
    }

    function _apply() {
        var path = WorkspaceCtrl.currentWorkspacePath
        if (mode === 0) {
            MergeCtrl.apply_union(path, unionTables.join(unitSep), targetField.text)
        } else if (mode === 1) {
            MergeCtrl.apply_dedup(path, dedupTable, dedupKeys.join(unitSep), targetField.text)
        } else {
            var joinParams = [
                joinLeft, joinRight, joinLeftKey, joinRightKey,
                howGroup.currentIndex === 1 ? "left" : "inner",
                targetField.text
            ]
            MergeCtrl.apply_join(path, joinParams.join(unitSep))
        }
    }

    // 工作区切换：重置选择并重载表列表
    Connections {
        target: WorkspaceCtrl
        onCurrent_changed: {
            page.unionTables = []
            page.dedupTable = ""
            page.dedupKeys = []
            page.joinLeft = ""
            page.joinRight = ""
            page.joinLeftKey = ""
            page.joinRightKey = ""
            MergeCtrl.load_tables(WorkspaceCtrl.currentWorkspacePath)
        }
    }

    // 页面可见时（首次加载）若已有工作区则加载表列表
    onVisibleChanged: {
        if (visible && WorkspaceCtrl.currentWorkspacePath)
            MergeCtrl.load_tables(WorkspaceCtrl.currentWorkspacePath)
    }

    // 控制器信号 → 顶部状态浮层
    Connections {
        target: MergeCtrl
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

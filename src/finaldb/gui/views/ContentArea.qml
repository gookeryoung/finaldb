import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FinalDB.Theme 1.0
import "pages"

Pane {
    id: contentArea
    objectName: "contentArea"
    property ThemeController theme: Theme
    padding: 0

    // 引用 Sidebar 以读取 currentPage
    property var sidebarRef: null
    property string activePage: sidebarRef ? sidebarRef.currentPage : "home"

    background: Rectangle {
        color: "transparent"
    }

    // 各非首页页面的「已加载」标志：首次访问后保持常驻，避免反复创建销毁。
    // 启动时仅构造 HomePage（首屏可见），其他页面在首次切换到时才加载。
    // 加载完成后保持 active=true，StackLayout 切换仍是 O(1)
    //（符合「复用控件，禁止反复创建销毁」约束）。
    property bool _cleanLoaded: false
    property bool _mergeLoaded: false
    property bool _historyLoaded: false
    property bool _statsLoaded: false
    property bool _settingsLoaded: false
    property bool _aboutLoaded: false

    readonly property var _pageIndex: ({
        "home": 0,
        "clean": 1,
        "merge": 2,
        "history": 3,
        "stats": 4,
        "settings": 5,
        "about": 6
    })

    StackLayout {
        id: stack
        anchors.fill: parent
        anchors.margins: theme.spacingLg
        currentIndex: contentArea._pageIndex[contentArea.activePage] ?? 0

        // 首次切换到非首页时命令式标记为已加载，之后常驻不卸载。
        // 在 onCurrentIndexChanged 中命令式赋值（active 绑定只读 _xxLoaded，
        // 写入路径不回到 active 绑定，避免 binding loop）。
        onCurrentIndexChanged: {
            switch (currentIndex) {
                case 1: contentArea._cleanLoaded = true; break
                case 2: contentArea._mergeLoaded = true; break
                case 3: contentArea._historyLoaded = true; break
                case 4: contentArea._statsLoaded = true; break
                case 5: contentArea._settingsLoaded = true; break
                case 6: contentArea._aboutLoaded = true; break
            }
        }

        // HomePage：启动首屏，立即加载
        HomePage {}

        // 其余页面：首次切换到时加载，之后常驻
        Loader {
            active: contentArea._cleanLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: CleanPage {}
        }
        Loader {
            active: contentArea._mergeLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: MergePage {}
        }
        Loader {
            active: contentArea._historyLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: HistoryPage {}
        }
        Loader {
            active: contentArea._statsLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: StatsPage {}
        }
        Loader {
            active: contentArea._settingsLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: SettingsPage {}
        }
        Loader {
            active: contentArea._aboutLoaded
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: AboutPage {}
        }
    }
}

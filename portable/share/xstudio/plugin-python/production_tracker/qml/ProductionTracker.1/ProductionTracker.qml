import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

import xStudio 1.0
import xstudio.qml.models 1.0

Rectangle {
    id: root
    color: "#222222"
    anchors.fill: parent

    // ======================================================================
    // Plugin data binding
    // ======================================================================

    XsModuleData {
        id: pluginData
        modelDataName: "Production Tracker"
    }

    // -- Attribute bindings --

    XsAttributeValue {
        id: connectionStatusAttr
        attributeTitle: "connection_status"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: authConfigAttr
        attributeTitle: "auth_config"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: projectsDataAttr
        attributeTitle: "projects_data"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: selectedProjectAttr
        attributeTitle: "selected_project"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: sequencesDataAttr
        attributeTitle: "sequences_data"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: shotsDataAttr
        attributeTitle: "shots_data"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: versionsDataAttr
        attributeTitle: "versions_data"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: commandAttr
        attributeTitle: "command_channel"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: statusMessageAttr
        attributeTitle: "status_message"
        model: pluginData
        role: "value"
    }

    XsAttributeValue {
        id: loadingAttr
        attributeTitle: "loading"
        model: pluginData
        role: "value"
    }

    // ======================================================================
    // Parsed data properties
    // ======================================================================

    property var connectionStatus: tryParse(connectionStatusAttr.value, {"connected": false})
    property var projectsList: tryParse(projectsDataAttr.value, [])
    property var selectedProject: tryParse(selectedProjectAttr.value, {"id": -1, "name": ""})
    property var sequencesList: tryParse(sequencesDataAttr.value, [])
    property var shotsList: tryParse(shotsDataAttr.value, [])
    property var versionsList: tryParse(versionsDataAttr.value, [])
    property string statusText: statusMessageAttr.value || ""
    property bool isLoading: loadingAttr.value || false

    // Track selection state locally
    property int selectedSequenceIndex: -1
    property int selectedShotIndex: -1
    property var selectedVersionIndices: []

    function tryParse(jsonStr, fallback) {
        if (!jsonStr || jsonStr === "") return fallback
        try {
            return JSON.parse(jsonStr)
        } catch(e) {
            return fallback
        }
    }

    function sendCommand(cmd) {
        commandAttr.value = JSON.stringify(cmd)
    }

    function getSelectedIds() {
        var ids = []
        for (var i = 0; i < selectedVersionIndices.length; i++) {
            var idx = selectedVersionIndices[i]
            var v = versionsList[idx]
            if (v && v.id) ids.push(v.id)
        }
        return ids
    }

    function toggleVersionSelection(index) {
        var sel = selectedVersionIndices.slice()
        var pos = sel.indexOf(index)
        if (pos !== -1) {
            sel.splice(pos, 1)
        } else {
            sel.push(index)
        }
        selectedVersionIndices = sel
    }

    function isVersionSelected(index) {
        return selectedVersionIndices.indexOf(index) !== -1
    }

    function statusColor(status) {
        if (!status) return "#888888"
        var s = status.toLowerCase()
        if (s === "apr" || s === "approved" || s === "final" || s === "fin")
            return "#4CAF50"
        if (s === "ip" || s === "in progress" || s === "in_progress")
            return "#FFC107"
        if (s === "rev" || s === "review" || s === "pending review" || s === "pen")
            return "#2196F3"
        if (s === "omt" || s === "omit" || s === "hold" || s === "hld")
            return "#F44336"
        if (s === "wtg" || s === "waiting" || s === "rdy" || s === "ready")
            return "#FF9800"
        return "#888888"
    }

    // ======================================================================
    // Layout
    // ======================================================================

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        // ------------------------------------------------------------------
        // Top bar: connection status + controls
        // ------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: "#2d2d2d"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                // Connection indicator dot
                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: connectionStatus.connected ? "#4CAF50" : "#F44336"
                }

                Text {
                    text: connectionStatus.connected
                        ? connectionStatus.backend + " - " + connectionStatus.user
                        : "Not Connected"
                    color: "#cccccc"
                    font.pixelSize: 12
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                // Connect / Disconnect button
                Rectangle {
                    width: 90; height: 24; radius: 3
                    color: connectBtnMouse.containsMouse ? "#555555" : "#3c3c3c"
                    border.color: "#555555"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: connectionStatus.connected ? "Disconnect" : "Connect"
                        color: "#cccccc"
                        font.pixelSize: 11
                    }

                    MouseArea {
                        id: connectBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (connectionStatus.connected) {
                                sendCommand({"action": "disconnect"})
                            } else {
                                connectionForm.visible = !connectionForm.visible
                            }
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------------
        // Connection form (toggled)
        // ------------------------------------------------------------------
        Rectangle {
            id: connectionForm
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? formColumn.implicitHeight + 20 : 0
            visible: false
            color: "#333333"
            clip: true

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 150 }
            }

            ColumnLayout {
                id: formColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 6

                Text {
                    text: "ShotGrid Connection"
                    color: "#bb9060"
                    font.pixelSize: 13
                    font.bold: true
                }

                // Site URL
                RowLayout {
                    spacing: 6
                    Text { text: "Site URL:"; color: "#aaaaaa"; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 3
                        color: "#2a2a2a"; border.color: "#555555"; border.width: 1
                        TextInput {
                            id: siteUrlInput
                            anchors.fill: parent; anchors.margins: 4
                            color: "#dddddd"; font.pixelSize: 11
                            selectByMouse: true; clip: true
                            text: {
                                var cfg = tryParse(authConfigAttr.value, {})
                                return cfg.site_url || ""
                            }
                        }
                    }
                }

                // Script Name
                RowLayout {
                    spacing: 6
                    Text { text: "Script Name:"; color: "#aaaaaa"; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 3
                        color: "#2a2a2a"; border.color: "#555555"; border.width: 1
                        TextInput {
                            id: scriptNameInput
                            anchors.fill: parent; anchors.margins: 4
                            color: "#dddddd"; font.pixelSize: 11
                            selectByMouse: true; clip: true
                            text: {
                                var cfg = tryParse(authConfigAttr.value, {})
                                return cfg.script_name || ""
                            }
                        }
                    }
                }

                // API Key
                RowLayout {
                    spacing: 6
                    Text { text: "API Key:"; color: "#aaaaaa"; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 3
                        color: "#2a2a2a"; border.color: "#555555"; border.width: 1
                        TextInput {
                            id: apiKeyInput
                            anchors.fill: parent; anchors.margins: 4
                            color: "#dddddd"; font.pixelSize: 11
                            selectByMouse: true; clip: true
                            echoMode: TextInput.Password
                        }
                    }
                }

                // Separator
                Rectangle {
                    Layout.fillWidth: true; height: 1; color: "#555555"
                }
                Text {
                    text: "-- or use login credentials --"
                    color: "#777777"; font.pixelSize: 10
                    Layout.alignment: Qt.AlignHCenter
                }

                // Login
                RowLayout {
                    spacing: 6
                    Text { text: "Login:"; color: "#aaaaaa"; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 3
                        color: "#2a2a2a"; border.color: "#555555"; border.width: 1
                        TextInput {
                            id: loginInput
                            anchors.fill: parent; anchors.margins: 4
                            color: "#dddddd"; font.pixelSize: 11
                            selectByMouse: true; clip: true
                        }
                    }
                }

                // Password
                RowLayout {
                    spacing: 6
                    Text { text: "Password:"; color: "#aaaaaa"; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 3
                        color: "#2a2a2a"; border.color: "#555555"; border.width: 1
                        TextInput {
                            id: passwordInput
                            anchors.fill: parent; anchors.margins: 4
                            color: "#dddddd"; font.pixelSize: 11
                            selectByMouse: true; clip: true
                            echoMode: TextInput.Password
                        }
                    }
                }

                // Connect button
                Rectangle {
                    Layout.alignment: Qt.AlignRight
                    width: 100; height: 28; radius: 3
                    color: formConnectMouse.containsMouse ? "#cc9060" : "#bb9060"

                    Text {
                        anchors.centerIn: parent
                        text: "Connect"
                        color: "#1a1a1a"
                        font.pixelSize: 12
                        font.bold: true
                    }

                    MouseArea {
                        id: formConnectMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            sendCommand({
                                "action": "connect",
                                "config": {
                                    "backend": "shotgrid",
                                    "site_url": siteUrlInput.text.trim(),
                                    "script_name": scriptNameInput.text.trim(),
                                    "api_key": apiKeyInput.text,
                                    "login": loginInput.text.trim(),
                                    "password": passwordInput.text
                                }
                            })
                            connectionForm.visible = false
                        }
                    }
                }

                // Error display
                Text {
                    visible: connectionStatus.error !== ""
                    text: connectionStatus.error || ""
                    color: "#F44336"
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        // ------------------------------------------------------------------
        // Main content area (split: navigation left, versions right)
        // ------------------------------------------------------------------
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            // ==============================================================
            // Left panel: hierarchy navigation
            // ==============================================================
            Rectangle {
                SplitView.preferredWidth: 240
                SplitView.minimumWidth: 160
                color: "#282828"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // -- Projects header + refresh --
                    Rectangle {
                        Layout.fillWidth: true; height: 28
                        color: "#2d2d2d"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8; anchors.rightMargin: 4
                            spacing: 4

                            Text {
                                text: "Projects"
                                color: "#bb9060"
                                font.pixelSize: 12
                                font.bold: true
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                width: 22; height: 22; radius: 3
                                color: refreshMouse.containsMouse ? "#555555" : "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: "\u21BB" // refresh arrow
                                    color: "#aaaaaa"
                                    font.pixelSize: 14
                                }

                                MouseArea {
                                    id: refreshMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: sendCommand({"action": "refresh_projects"})
                                }
                            }
                        }
                    }

                    // -- Project list --
                    ListView {
                        id: projectList
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(contentHeight, 140)
                        Layout.maximumHeight: 140
                        clip: true
                        model: projectsList.length

                        delegate: Rectangle {
                            width: projectList.width
                            height: 26
                            color: {
                                var proj = projectsList[index]
                                if (proj && proj.id === selectedProject.id)
                                    return "#3c3c3c"
                                return projMouse.containsMouse ? "#333333" : "transparent"
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 8
                                spacing: 6

                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: statusColor(projectsList[index] ? projectsList[index].sg_status : "")
                                }

                                Text {
                                    text: projectsList[index] ? projectsList[index].name : ""
                                    color: "#dddddd"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: projMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var proj = projectsList[index]
                                    if (proj) {
                                        selectedSequenceIndex = -1
                                        selectedShotIndex = -1
                                        selectedVersionIndices = []
                                        sendCommand({
                                            "action": "select_project",
                                            "project_id": proj.id,
                                            "project_name": proj.name
                                        })
                                    }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            anchors.centerIn: parent
                            visible: projectsList.length === 0
                            text: connectionStatus.connected ? "No projects" : "Connect to browse"
                            color: "#666666"
                            font.pixelSize: 11
                        }
                    }

                    // -- Separator --
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#3c3c3c" }

                    // -- Sequences header --
                    Rectangle {
                        Layout.fillWidth: true; height: 24
                        color: "#2d2d2d"
                        visible: selectedProject.id > 0

                        Text {
                            anchors.left: parent.left; anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Sequences"
                            color: "#bb9060"
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    // -- Sequence list --
                    ListView {
                        id: sequenceList
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(contentHeight, 120)
                        Layout.maximumHeight: 120
                        clip: true
                        visible: selectedProject.id > 0
                        model: sequencesList.length

                        delegate: Rectangle {
                            width: sequenceList.width
                            height: 24
                            color: index === selectedSequenceIndex
                                ? "#3c3c3c"
                                : seqMouse.containsMouse ? "#333333" : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 8
                                spacing: 6

                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: statusColor(sequencesList[index] ? sequencesList[index].sg_status : "")
                                }

                                Text {
                                    text: sequencesList[index] ? sequencesList[index].code : ""
                                    color: "#dddddd"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: seqMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var seq = sequencesList[index]
                                    if (seq) {
                                        selectedSequenceIndex = index
                                        selectedShotIndex = -1
                                        selectedVersionIndices = []
                                        sendCommand({
                                            "action": "select_sequence",
                                            "project_id": selectedProject.id,
                                            "sequence_id": seq.id
                                        })
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: sequencesList.length === 0 && selectedProject.id > 0
                            text: "No sequences"
                            color: "#666666"
                            font.pixelSize: 11
                        }
                    }

                    // -- Separator --
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#3c3c3c" }

                    // -- Shots header --
                    Rectangle {
                        Layout.fillWidth: true; height: 24
                        color: "#2d2d2d"
                        visible: selectedSequenceIndex >= 0

                        Text {
                            anchors.left: parent.left; anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Shots"
                            color: "#bb9060"
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    // -- Shot list --
                    ListView {
                        id: shotList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        visible: selectedSequenceIndex >= 0
                        model: shotsList.length

                        delegate: Rectangle {
                            width: shotList.width
                            height: 24
                            color: index === selectedShotIndex
                                ? "#3c3c3c"
                                : shotMouse.containsMouse ? "#333333" : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 8
                                spacing: 6

                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: statusColor(shotsList[index] ? shotsList[index].sg_status : "")
                                }

                                Text {
                                    text: shotsList[index] ? shotsList[index].code : ""
                                    color: "#dddddd"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: shotMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var shot = shotsList[index]
                                    if (shot) {
                                        selectedShotIndex = index
                                        selectedVersionIndices = []
                                        sendCommand({
                                            "action": "select_shot",
                                            "shot_id": shot.id
                                        })
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: shotsList.length === 0 && selectedSequenceIndex >= 0
                            text: "No shots"
                            color: "#666666"
                            font.pixelSize: 11
                        }
                    }

                    // -- Spacer if nothing visible --
                    Item {
                        Layout.fillHeight: true
                        visible: selectedProject.id <= 0
                    }
                }
            }

            // ==============================================================
            // Right panel: versions list
            // ==============================================================
            Rectangle {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 200
                color: "#282828"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // -- Versions header + search --
                    Rectangle {
                        Layout.fillWidth: true; height: 32
                        color: "#2d2d2d"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 6

                            Text {
                                text: "Versions"
                                color: "#bb9060"
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                text: "(" + versionsList.length + ")"
                                color: "#888888"
                                font.pixelSize: 11
                            }

                            Item { Layout.fillWidth: true }

                            // Search field
                            Rectangle {
                                width: 180; height: 22; radius: 3
                                color: "#2a2a2a"
                                border.color: searchInput.activeFocus ? "#bb9060" : "#555555"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 3
                                    spacing: 4

                                    Text {
                                        text: "\uD83D\uDD0D"
                                        font.pixelSize: 10
                                        color: "#888888"
                                    }

                                    TextInput {
                                        id: searchInput
                                        Layout.fillWidth: true
                                        color: "#dddddd"
                                        font.pixelSize: 11
                                        selectByMouse: true
                                        clip: true

                                        Text {
                                            anchors.fill: parent
                                            text: "Search versions..."
                                            color: "#555555"
                                            font.pixelSize: 11
                                            visible: !searchInput.text && !searchInput.activeFocus
                                        }

                                        onAccepted: {
                                            if (text.trim() !== "" && selectedProject.id > 0) {
                                                sendCommand({
                                                    "action": "search",
                                                    "project_id": selectedProject.id,
                                                    "query": text.trim()
                                                })
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // -- Version list --
                    ListView {
                        id: versionList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: versionsList.length
                        spacing: 1

                        delegate: Rectangle {
                            width: versionList.width
                            height: 52
                            color: isVersionSelected(index)
                                ? "#3d3525"
                                : verMouse.containsMouse ? "#333333" : "#2a2a2a"
                            border.color: isVersionSelected(index) ? "#bb9060" : "transparent"
                            border.width: isVersionSelected(index) ? 1 : 0

                            property var ver: versionsList[index] || {}

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 6
                                spacing: 8

                                // Status indicator
                                Rectangle {
                                    width: 4
                                    Layout.fillHeight: true
                                    radius: 2
                                    color: statusColor(ver.sg_status_list || "")
                                }

                                // Version info
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    RowLayout {
                                        spacing: 6

                                        Text {
                                            text: ver.code || "Unknown"
                                            color: "#eeeeee"
                                            font.pixelSize: 12
                                            font.bold: true
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        // Status badge
                                        Rectangle {
                                            visible: (ver.sg_status_list || "") !== ""
                                            width: statusBadgeText.implicitWidth + 10
                                            height: 16
                                            radius: 8
                                            color: statusColor(ver.sg_status_list || "")
                                            opacity: 0.8

                                            Text {
                                                id: statusBadgeText
                                                anchors.centerIn: parent
                                                text: ver.sg_status_list || ""
                                                color: "#ffffff"
                                                font.pixelSize: 9
                                                font.bold: true
                                            }
                                        }
                                    }

                                    RowLayout {
                                        spacing: 12

                                        Text {
                                            text: {
                                                var user = ver.user
                                                if (!user) return ""
                                                if (typeof user === "object") return user.name || ""
                                                return String(user)
                                            }
                                            color: "#999999"
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: {
                                                var dt = ver.created_at || ""
                                                if (!dt) return ""
                                                // Show date portion
                                                return dt.substring(0, 10)
                                            }
                                            color: "#777777"
                                            font.pixelSize: 10
                                        }

                                        Text {
                                            visible: (ver.frame_range || "") !== ""
                                            text: "Frames: " + (ver.frame_range || "")
                                            color: "#777777"
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: verMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: function(mouse) {
                                    if (mouse.modifiers & Qt.ControlModifier) {
                                        toggleVersionSelection(index)
                                    } else {
                                        selectedVersionIndices = [index]
                                    }
                                }
                                onDoubleClicked: {
                                    // Double-click plays immediately
                                    var v = versionsList[index]
                                    if (v) {
                                        sendCommand({
                                            "action": "play_selected",
                                            "version_ids": [v.id]
                                        })
                                    }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            anchors.centerIn: parent
                            visible: versionsList.length === 0
                            text: {
                                if (!connectionStatus.connected) return "Connect to browse"
                                if (selectedProject.id <= 0) return "Select a project"
                                if (selectedShotIndex < 0) return "Select a shot to see versions"
                                return "No versions found"
                            }
                            color: "#666666"
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------------
        // Bottom bar: status + load button
        // ------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: "#2d2d2d"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                // Loading indicator
                Text {
                    visible: isLoading
                    text: "\u23F3"
                    font.pixelSize: 12
                    color: "#bb9060"

                    SequentialAnimation on opacity {
                        running: isLoading
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
                    }
                }

                // Status text
                Text {
                    text: statusText
                    color: "#999999"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Selection count
                Text {
                    visible: selectedVersionIndices.length > 0
                    text: selectedVersionIndices.length + " selected"
                    color: "#bb9060"
                    font.pixelSize: 11
                }

                // Add to Playlist button
                Rectangle {
                    visible: selectedVersionIndices.length > 0
                    width: addLabel.implicitWidth + 16; height: 24; radius: 3
                    color: addBtnMouse.containsMouse ? "#555555" : "#3c3c3c"
                    border.color: "#666666"; border.width: 1

                    Text {
                        id: addLabel
                        anchors.centerIn: parent
                        text: "+ Playlist"
                        color: "#cccccc"
                        font.pixelSize: 11
                    }

                    MouseArea {
                        id: addBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var ids = getSelectedIds()
                            if (ids.length > 0)
                                sendCommand({"action": "add_to_playlist", "version_ids": ids})
                        }
                    }
                }

                // Add to Timeline button
                Rectangle {
                    visible: selectedVersionIndices.length > 0
                    width: tlLabel.implicitWidth + 16; height: 24; radius: 3
                    color: tlBtnMouse.containsMouse ? "#555555" : "#3c3c3c"
                    border.color: "#666666"; border.width: 1

                    Text {
                        id: tlLabel
                        anchors.centerIn: parent
                        text: "+ Timeline"
                        color: "#cccccc"
                        font.pixelSize: 11
                    }

                    MouseArea {
                        id: tlBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var ids = getSelectedIds()
                            if (ids.length > 0)
                                sendCommand({"action": "add_to_timeline", "version_ids": ids})
                        }
                    }
                }

                // Compare button (2+ selected)
                Rectangle {
                    visible: selectedVersionIndices.length >= 2
                    width: cmpLabel.implicitWidth + 16; height: 24; radius: 3
                    color: cmpBtnMouse.containsMouse ? "#555555" : "#3c3c3c"
                    border.color: "#2196F3"; border.width: 1

                    Text {
                        id: cmpLabel
                        anchors.centerIn: parent
                        text: selectedVersionIndices.length === 2 ? "A/B" : "Grid"
                        color: "#2196F3"
                        font.pixelSize: 11
                        font.bold: true
                    }

                    MouseArea {
                        id: cmpBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var ids = getSelectedIds()
                            if (ids.length >= 2) {
                                sendCommand({
                                    "action": "compare",
                                    "version_ids": ids,
                                    "mode": "auto"
                                })
                            }
                        }
                    }
                }

                // Play Selected button (primary action)
                Rectangle {
                    visible: selectedVersionIndices.length > 0
                    width: playLabel.implicitWidth + 20; height: 24; radius: 3
                    color: playBtnMouse.containsMouse ? "#cc9060" : "#bb9060"

                    Text {
                        id: playLabel
                        anchors.centerIn: parent
                        text: "\u25B6 Play"
                        color: "#1a1a1a"
                        font.pixelSize: 11
                        font.bold: true
                    }

                    MouseArea {
                        id: playBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var ids = getSelectedIds()
                            if (ids.length > 0)
                                sendCommand({"action": "play_selected", "version_ids": ids})
                        }
                    }
                }
            }
        }
    }
}

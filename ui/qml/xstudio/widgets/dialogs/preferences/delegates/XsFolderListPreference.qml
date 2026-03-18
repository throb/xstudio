// SPDX-License-Identifier: Apache-2.0
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

import xstudio.qml.models 1.0
import xStudio 1.0

import "../widgets"

ColumnLayout {
    width: parent.width
    spacing: 4

    RowLayout {
        Layout.fillWidth: true
        height: XsStyleSheet.widgetStdHeight

        XsLabel {
            Layout.alignment: Qt.AlignVCenter|Qt.AlignRight
            Layout.preferredWidth: prefsLabelWidth
            Layout.maximumWidth: prefsLabelWidth
            wrapMode: Text.NoWrap
            elide: Text.ElideLeft
            text: displayNameRole ? displayNameRole : nameRole
            horizontalAlignment: Text.AlignRight
        }

        XsPrimaryButton {
            Layout.fillHeight: true
            text: "Add Folder..."
            onClicked: {
                dialogHelpers.showFolderDialog(
                    addFolder,
                    "",
                    "Select Plugin Folder")
            }
        }

        XsPreferenceInfoButton {
        }
    }

    Repeater {
        model: valueRole ? valueRole : []

        RowLayout {
            Layout.fillWidth: true
            height: XsStyleSheet.widgetStdHeight

            Item {
                Layout.preferredWidth: prefsLabelWidth
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: XsStyleSheet.panelBgColor
                radius: 2

                XsText {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    text: modelData
                    elide: Text.ElideMiddle
                    verticalAlignment: Text.AlignVCenter
                    color: XsStyleSheet.secondaryTextColor
                }
            }

            XsSecondaryButton {
                Layout.fillHeight: true
                text: "X"
                onClicked: removeFolder(index)
            }
        }
    }

    function addFolder(path) {
        if (path === undefined || path === false) return
        var folders = valueRole ? JSON.parse(JSON.stringify(valueRole)) : []
        var folderStr = path.toString()
        // strip file:// prefix from URL
        if (folderStr.startsWith("file://")) {
            folderStr = folderStr.substring(7)
        }
        if (folders.indexOf(folderStr) === -1) {
            folders.push(folderStr)
            valueRole = folders
        }
    }

    function removeFolder(idx) {
        var folders = JSON.parse(JSON.stringify(valueRole))
        folders.splice(idx, 1)
        valueRole = folders
    }
}

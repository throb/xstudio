// SPDX-License-Identifier: Apache-2.0
import QtQuick
import QtQuick.Layouts

import xStudio 1.0
import xstudio.qml.models 1.0

Item {

	id: bmd_settings_dialog
    property var dockWidgetSize: XsStyleSheet.primaryButtonStdHeight + 4

    // this is REQUIRED to ensure correct scaling
    anchors.fill: parent

    XsGradientRectangle{
        anchors.fill: parent
    }

}
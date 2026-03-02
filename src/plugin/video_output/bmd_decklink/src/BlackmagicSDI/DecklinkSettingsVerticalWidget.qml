// SPDX-License-Identifier: Apache-2.0
import QtQuick
import QtQuick.Layouts

import xStudio 1.0
import xstudio.qml.models 1.0

Item {

	id: bmd_settings_dialog

    // this property is REQUIRED to set the docking widget size
    property var dockWidgetSize: 120

    // this is REQUIRED to ensure correct scaling
    anchors.fill: parent

    XsGradientRectangle {
        anchors.fill: bmd_settings_dialog
    }

    XsModuleData {
        id: decklink_settings
        modelDataName: "Decklink Settings"
    }

    XsModuleData {
        id: decklink_viewport_attributes
        modelDataName: "BMDecklinkPlugin viewport_toolbar"
    }

    XsAttributeValue {
        id: __decklinkEnabled
        attributeTitle: "Enabled"
        model: decklink_settings
    }
    property alias is_running: __decklinkEnabled.value

    XsAttributeValue {
        id: __startStop
        attributeTitle: "Start Stop"
        model: decklink_settings
    }
    property alias startStop: __startStop.value

    property var maxBoxWidth: 30

    ListModel{ 
        id: bmd_settings_attr_model


    }

    property real button_radius: 3

    Item {

        anchors.fill: parent
        anchors.margins: 5

        ColumnLayout {

            anchors.fill: parent
            spacing: 10

            XsText {
                text: "SDI Controls"
                font.weight: Font.Bold
                font.pixelSize: XsStyleSheet.fontSize
                font.family: XsStyleSheet.fontFamily
                Layout.alignment: Qt.AlignHCenter
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: XsStyleSheet.widgetBgNormalColor
            }

            Item {
                height: 5
            }

            XsText {
                text: "SDI Output"
                font.pixelSize: XsStyleSheet.fontSize
                font.family: XsStyleSheet.fontFamily
                Layout.alignment: Qt.AlignLeft
            }

            Item {

                id: startStopButton
                Layout.preferredHeight: 20
                Layout.preferredWidth: 80
                Layout.alignment: Qt.AlignHCenter | Qt.AlignLeft

                Rectangle {
                    height: parent.height
                    width: parent.width/2
                    color: "#900"
                    radius: button_radius
                    XsText {
                        text: "Off"
                        anchors.centerIn: parent
                        font.weight: Font.Bold
                        font.pixelSize: 10
                    }
                }
        
                Rectangle {
                    height: parent.height
                    width: 10
                    color: is_running ? "#090" : "#900"
                    x: parent.width/2-button_radius
                }

                Rectangle {
                    height: parent.height
                    width: parent.width/2
                    x: width
                    color: "#090"
                    radius: button_radius
                    XsText {
                        text: "On"
                        anchors.centerIn: parent
                        font.weight: Font.Bold
                        font.pixelSize: 10
                    }
                }

                Rectangle {
                    height: parent.height
                    width: parent.width/2
                    x: is_running ? 0 : width
                    color: "#333"
                    radius: button_radius
                    border.color: "#888"
                    border.width: 2
                    Behavior on x {NumberAnimation {duration: 50}}
                }

                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    radius: button_radius
                    border.color: mouseArea2.containsMouse ? palette.highlight : "transparent"
                    border.width: 1
                }

                MouseArea {
                    id: mouseArea2
                    hoverEnabled: true
                    anchors.fill: startStopButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // toggling the start stop value to get a callback on the C++
                        // side to toggle SDI output. That actual value of startStop
                        // is not important!
                        startStop = !startStop
                    }
                }
            }

            Item {
                Layout.preferredHeight: 30
            }

            DecklinkMultichoiceSetting {
                Layout.fillWidth: true
                label_text: "Display (Colour)"
                attrs_model: decklink_viewport_attributes
                attr_name: "Display"  
            }

            DecklinkMultichoiceSetting {
                Layout.fillWidth: true
                label_text: "Image Fit Mode"
                attrs_model: decklink_viewport_attributes
                attr_name: "Fit (F)"
                enabled: !link_toggle.attr_value
            }

            DecklinkToggleSetting {
                id: link_toggle
                display_name: "Track Zoom/Pan"
                toggle_attr_name: "Track Viewport"
            }
        
            RowLayout {
                spacing: 10
                XsLabel {
                    text: "Status"
                    Layout.alignment: Qt.AlignLeft
                }

                DecklinkStatusIndicator {
                    Layout.alignment: Qt.AlignLeft
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                }

            }

            Item {
                Layout.preferredHeight: 30
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: XsStyleSheet.widgetBgNormalColor
            }

            RowLayout {

                Layout.fillWidth:  true
                spacing: 10

                XsSecondaryButton{
    
                    id: subsetBtn
                    z: 100
                    imgSrc: "qrc:/icons/chevron_right.svg"
                    width: 20
                    height: 20
                    rotation: advanced_settings.visible ? 90:0
                    imageSrcSize: width
                    Behavior on rotation {NumberAnimation{duration: 150 }}
                    bgColorPressed: bgColorNormal
                    onClicked:{
                        advanced_settings.visible = !advanced_settings.visible
                    }
    
                }

                XsLabel {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignLeft
                    height: 1
                    text: "Advanced"
                }
        
            }

            ColumnLayout {

                spacing: 10
                id: advanced_settings
                Layout.fillWidth: true
                visible: false
    
                DecklinkMultichoiceSetting {
                    Layout.fillWidth: true
                    label_text: "Output Res."
                    attrs_model: decklink_settings
                    attr_name: "Output Resolution"
                    enabled: !is_running
                }
    
                DecklinkMultichoiceSetting {
                    Layout.fillWidth: true
                    label_text: "Refresh Rate"
                    attrs_model: decklink_settings
                    attr_name: "Refresh Rate"
                    enabled: !is_running
                }

                DecklinkMultichoiceSetting {
                    Layout.fillWidth: true
                    label_text: "Pixel Format" 
                    attrs_model: decklink_settings
                    attr_name: "Pixel Format" 
                    enabled: !is_running
                }

                DecklinkIntegerSetting {
                    integer_attr_name: "Audio Sync Delay"
                    display_name: "Audio Delay / msec"
                }
                    
                DecklinkIntegerSetting {
                    integer_attr_name: "Video Sync Delay"
                    display_name: "Video Delay / msec"
                }

                DecklinkToggleSetting {
                    display_name: "Mute PC Audio"
                    toggle_attr_name: "Auto Disable PC Audio"
                }

            }

            Item {
                Layout.fillHeight: true
            }
        }
    }

}
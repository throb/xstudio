import QtQml
import xstudio.qml.helpers 1.0
import xstudio.qml.models 1.0

XsModelProperty {

    role: "value"
    property var model
    property string attributeTitle: ""
    index: model ? model.searchRecursive(attributeTitle, "title") : null
    property var modelLength: model ? model.length : 0
    property var connectedModel: null
    signal indexBecameValid()

    function handleTrackedModelChanged() {
        update_index()
    }

    function reconnectModelSignals() {
        if (connectedModel) {
            try {
                connectedModel.jsonChanged.disconnect(handleTrackedModelChanged)
            } catch (err) {}
            try {
                connectedModel.modelDataNameChanged.disconnect(handleTrackedModelChanged)
            } catch (err) {}
        }

        connectedModel = model

        if (connectedModel) {
            try {
                connectedModel.jsonChanged.connect(handleTrackedModelChanged)
            } catch (err) {}
            try {
                connectedModel.modelDataNameChanged.connect(handleTrackedModelChanged)
            } catch (err) {}
        }
    }

    Component.onCompleted: {
        reconnectModelSignals()
        update_index()
    }

    Component.onDestruction: {
        if (connectedModel) {
            try {
                connectedModel.jsonChanged.disconnect(handleTrackedModelChanged)
            } catch (err) {}
            try {
                connectedModel.modelDataNameChanged.disconnect(handleTrackedModelChanged)
            } catch (err) {}
        }
    }

    onAttributeTitleChanged: {
        update_index()
    }

    onModelChanged: {
        reconnectModelSignals()
        update_index()
    }

    onModelLengthChanged: {
        update_index()
    }

    function update_index() {
        if (model) {
            var was_valid = index.valid
            index = model.searchRecursive(attributeTitle, "title")
            if (!was_valid && index.valid) {
                indexBecameValid()
            }
        }
    }

}

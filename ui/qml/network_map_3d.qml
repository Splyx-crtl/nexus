// D2: the 3D network map. All node/link positions, colors and states are precomputed in Python
// (ui/network_map_3d.py's Network3DBridge, built on ui/map3d_geometry.py's pure math) and exposed here as the
// "bridge" context property - this file does no vector math of its own, only binds numbers to QtQuick3D models.
import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

Item {
    id: root

    View3D {
        id: view3d
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#03080a"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.Medium
            tonemapMode: SceneEnvironment.TonemapModeNone
        }

        Node {
            id: cameraOrigin
            eulerRotation: Qt.vector3d(-20, 25, 0)
            PerspectiveCamera {
                id: camera
                z: 11
                clipNear: 0.1
                clipFar: 1000
            }
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-35, -35, 0)
            brightness: 1.6
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(40, 140, 0)
            brightness: 0.5
        }

        // -- links --------------------------------------------------------------------------------------------
        Repeater3D {
            model: bridge ? bridge.links : []
            delegate: Model {
                required property var modelData
                source: "#Cylinder"
                position: Qt.vector3d(modelData.mx, modelData.my, modelData.mz)
                rotation: Qt.quaternion(modelData.qw, modelData.qx, modelData.qy, modelData.qz)
                // Qt Quick 3D's built-in primitives are modeled at a 100-unit scale, not 1 unit - so a 0.035
                // world-unit radius needs scale 0.035/100, and a world-length link needs length/100 on the Y axis.
                scale: Qt.vector3d(0.00035, modelData.length / 100, 0.00035)
                materials: PrincipledMaterial {
                    baseColor: modelData.color
                    lighting: PrincipledMaterial.NoLighting
                    opacity: modelData.active ? 0.9 : 0.6
                }
            }
        }

        // -- data-flow pulses on the active link(s) only -------------------------------------------------------
        Repeater3D {
            model: bridge ? bridge.links.filter(function(l) { return l.active }) : []
            delegate: Node {
                required property var modelData
                property real t: 0
                SequentialAnimation on t {
                    loops: Animation.Infinite
                    running: true
                    NumberAnimation { from: 0; to: 1; duration: 1100; easing.type: Easing.InOutQuad }
                }
                position: Qt.vector3d(modelData.ax + (modelData.bx - modelData.ax) * t,
                                      modelData.ay + (modelData.by - modelData.ay) * t,
                                      modelData.az + (modelData.bz - modelData.az) * t)
                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.0009, 0.0009, 0.0009)
                    materials: PrincipledMaterial {
                        baseColor: "#22d3ee"
                        lighting: PrincipledMaterial.NoLighting
                        emissiveFactor: Qt.vector3d(1.2, 1.2, 1.2)
                    }
                }
            }
        }

        // -- nodes ----------------------------------------------------------------------------------------------
        Repeater3D {
            model: bridge ? bridge.nodes : []
            delegate: Node {
                required property var modelData
                position: Qt.vector3d(modelData.x, modelData.y, modelData.z)
                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.0022, 0.0022, 0.0022)
                    materials: PrincipledMaterial {
                        baseColor: modelData.color
                        lighting: PrincipledMaterial.NoLighting
                        emissiveFactor: Qt.vector3d(modelData.glow, modelData.glow, modelData.glow)
                    }
                }
            }
        }

        // -- trace wave: an expanding, fading ring around the current node while heat is elevated ----------------
        Node {
            id: traceWave
            visible: bridge ? bridge.traceActive : false
            position: bridge ? Qt.vector3d(bridge.currentX, bridge.currentY, bridge.currentZ) : Qt.vector3d(0, 0, 0)
            property real t: 0
            SequentialAnimation on t {
                loops: Animation.Infinite
                running: traceWave.visible
                NumberAnimation { from: 0; to: 1; duration: 1400; easing.type: Easing.OutCubic }
            }
            Model {
                source: "#Sphere"
                scale: Qt.vector3d((0.15 + traceWave.t * 1.3) / 100, 0.04 / 100, (0.15 + traceWave.t * 1.3) / 100)
                materials: PrincipledMaterial {
                    baseColor: "#ff3860"
                    lighting: PrincipledMaterial.NoLighting
                    opacity: Math.max(0, 0.6 * (1 - traceWave.t))
                }
            }
        }
    }

    OrbitCameraController {
        anchors.fill: parent
        origin: cameraOrigin
        camera: camera
        yInvert: true
    }
}

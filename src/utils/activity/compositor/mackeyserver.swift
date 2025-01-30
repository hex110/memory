import AppKit
import CoreGraphics
import Darwin.C
import Foundation
import Swift

// How long to wait before timing out a key response
let timeoutTime: Int64 = 30

// Virtual key codes for modifier keys (you might need others, see the link in comments below)
let VK_LCOMMAND: Int64 = 0x37
let VK_RCOMMAND: Int64 = 0x36
let VK_LSHIFT: Int64 = 0x38
let VK_RSHIFT: Int64 = 0x3C
let VK_LALT: Int64 = 0x3A
let VK_RALT: Int64 = 0x3D
let VK_LCTRL: Int64 = 0x3B
let VK_RCTRL: Int64 = 0x3E
let VK_CAPSLOCK: Int64 = 0x39
let VK_FN: Int64 = 0x3F

/*
  Semaphore-based timeout mechanism.
 */
let signalMutex = DispatchSemaphore(value: 1)
let requestTimeoutSemaphore = DispatchSemaphore(value: 0)
let responseSemaphore = DispatchSemaphore(value: 0)
var requestTime: Int64 = 0
var responseId: Int64 = 0
var timeoutId: Int64 = 0
var curId: Int64 = 0
var output: String = ""

/// getMillis
/// Obtain milliseconds since 1970.
/// @returns Milliseconds since 1970
func getMillis() -> Int64 {
    return Int64(NSDate().timeIntervalSince1970 * 1000)
}

/// haltPropogation
/// Communicates key information with the calling process to identify whether the key event should
/// be propogated to the rest of the OS.
/// @param key    - The key code pressed.
/// @param isDown - true, if a keydown event occurred, false otherwise.
/// @returns Whether the event should be propogated or not.
/// @remark Sends a comma delimited string of the form "keyCode,DOWN,eventID"  or "keyCode,UP,eventID".
///  Expects "1\n" (halt propogation of event) or "0\n" (do not halt propogation of event)
/// @remark This function timeouts after  30ms and returns false in order to propogate the event to the rest of the OS.
func haltPropogation(
    isMouse: Bool,
    isDown: Bool,
    keyCode: Int64,
    location: (Double, Double),
    flags: String = ""
) -> Bool {
    curId = curId + 1
    if isMouse {
        print("MOUSE,\(isDown ? "DOWN" : "UP"),\(keyCode),\(location.0),\(location.1),\(curId)")
    } else {
        print("KEYBOARD,\(isDown ? "DOWN" : "UP"),\(keyCode),\(location.0),\(location.1),\(curId),\(flags)")
    }
    
    fflush(stdout)

    // Indicate when the next timeout should occur
    requestTime = getMillis() + timeoutTime
    requestTimeoutSemaphore.signal()

    // Wait for any response
    responseSemaphore.wait()

    return output == "1"
}

/// Synchronously reads a line from the stdin and tries to report the result to the haltPropogation function (if it hasn't
/// timed out already)
func checkInputLoop() {
    while true {
        // Retrieve input and extract the code
        guard let line: String = readLine(strippingNewline: true) else { return }
        let parts = line.components(separatedBy: ",")
        let code = parts[0]
        let id = Int64(parts[1]) ?? 0

        // Lock the signalling, making sure the timeout doesn't signal it's response yet
        signalMutex.wait()
        if timeoutId < id {
            // Set the output and signal that there is a response
            responseId = id
            output = code
            responseSemaphore.signal()
        }
        signalMutex.signal()
    }
}

/// Synchronously waits until a timeout occurs and reports this to the haltPropogation function if it hasn't received a response
/// yet.
func timeoutLoop() {
    while true {
        // Wait for a timeout to be requested
        requestTimeoutSemaphore.wait()

        // Calculate how long to sleep in order to wake up at the requested time and start sleeping
        let sleepDuration = requestTime - getMillis()
        if sleepDuration > 0 {
            usleep(UInt32(sleepDuration) * 1000)
        }

        // Lock the signalling, making sure the input signalling can't happen before we finished here
        signalMutex.wait()
        timeoutId = timeoutId + 1
        if responseId < timeoutId {
            // Set the output to 0 and signal that there is a response
            output = "0"
            responseSemaphore.signal()
        }
        signalMutex.signal()
    }
}

/// Prints to stderr for error reporting purposes
/// @param data - Text data to log to stderr
func logErr(_ data: String) {
    fputs("\(data)\n", stderr)
    fflush(stderr)
}

/// Returns true if key event passed is a onDown message otherwise returns false.
/// @param event - Key event received
/// @param keyCode - scanCode of the key pressed
/// @returns True if key is down message, false if key is up message
func getModifierDownState(event: CGEvent, keyCode: Int64) -> Bool {
    switch keyCode {
    case VK_LCOMMAND, VK_RCOMMAND:
        return event.flags.contains(.maskCommand)
    case VK_LSHIFT, VK_RSHIFT:
        return event.flags.contains(.maskShift)
    case VK_LCTRL, VK_RCTRL:
        return event.flags.contains(.maskControl)
    case VK_LALT, VK_RALT:
        return event.flags.contains(.maskAlternate)
    case VK_CAPSLOCK:
        return event.flags.contains(.maskAlphaShift)
    case VK_FN:
        return event.flags.contains(.maskSecondaryFn)
    default:
        return false
    }
}

// Helper function to get modifier flags in a string format
func getModifierFlags(event: CGEvent) -> String {
    var flags: [String] = []
    if event.flags.contains(.maskCommand) {
        flags.append("CMD")
    }
    if event.flags.contains(.maskShift) {
        flags.append("SHIFT")
    }
    if event.flags.contains(.maskControl) {
        flags.append("CTRL")
    }
    if event.flags.contains(.maskAlternate) {
        flags.append("ALT")
    }
    if event.flags.contains(.maskSecondaryFn) {
        flags.append("FN")
    }
    // Add other flags if needed
    return flags.joined(separator: "+")
}

/// Gets the name of the currently active application
func getActiveAppName() -> String {
    if let app = NSWorkspace.shared.frontmostApplication {
        return app.localizedName ?? "Unknown"
    }
    return "Unknown"
}

/// Gets information about the currently active window
func getActiveWindowInfo() -> [String: Any]? {
    guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
        return nil
    }

    let frontmostAppPid = frontmostApp.processIdentifier

    // Get the list of all windows
    guard let windowList = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as? [[String: AnyObject]] else {
        return nil
    }

    for window in windowList {
        guard let windowOwnerPid = window[kCGWindowOwnerPID as String] as? Int32,
              windowOwnerPid == frontmostAppPid else {
            continue
        }

        // Check if it's the active window (layer 0 usually indicates the active window)
        if let windowLayer = window[kCGWindowLayer as String] as? Int, windowLayer == 0 {
            let bounds = CGRect(dictionaryRepresentation: window[kCGWindowBounds as String] as! CFDictionary)!

            var windowInfo: [String: Any] = [
                "ownerName": window[kCGWindowOwnerName as String] as? String ?? "Unknown",
                "windowName": window[kCGWindowName as String] as? String ?? "",
                "windowNumber": window[kCGWindowNumber as String] as? Int ?? -1,
                "windowLayer": windowLayer,
                "boundsX": bounds.origin.x,
                "boundsY": bounds.origin.y,
                "boundsWidth": bounds.width,
                "boundsHeight": bounds.height,
                "windowMemoryUsage": window[kCGWindowMemoryUsage as String] as? Int ?? -1
            ]
            return windowInfo
        }
    }

    return nil
}

/// Gets information about all visible windows
func getAllWindows() -> [[String: Any]] {
    guard let windowList = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: AnyObject]] else {
        return []
    }

    var windowInfoList: [[String: Any]] = []

    for window in windowList {
        guard let ownerName = window[kCGWindowOwnerName as String] as? String,
              let windowName = window[kCGWindowName as String] as? String,
              let windowNumber = window[kCGWindowNumber as String] as? Int,
              let windowLayer = window[kCGWindowLayer as String] as? Int
        else {
            continue
        }

        let bounds = CGRect(dictionaryRepresentation: window[kCGWindowBounds as String] as! CFDictionary)!

        let windowInfo: [String: Any] = [
            "ownerName": ownerName,
            "windowName": windowName,
            "windowNumber": windowNumber,
            "windowLayer": windowLayer,
            "boundsX": bounds.origin.x,
            "boundsY": bounds.origin.y,
            "boundsWidth": bounds.width,
            "boundsHeight": bounds.height,
            "windowMemoryUsage": window[kCGWindowMemoryUsage as String] as? Int ?? -1
        ]
        windowInfoList.append(windowInfo)
    }

    return windowInfoList
}

// Add a helper extension to format dictionaries as JSON strings
extension Dictionary {
    var jsonString: String? {
        guard let data = try? JSONSerialization.data(withJSONObject: self, options: []) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
}

extension Array {
    var jsonString: String? {
        guard let data = try? JSONSerialization.data(withJSONObject: self, options: []) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
}

/// myCGEventTapCallback
func myCGEventTapCallback(
    proxy: CGEventTapProxy, type: CGEventType, event: CGEvent, refcon: UnsafeMutableRawPointer?
) -> Unmanaged<CGEvent>? {

    // Handle window info events
    if type == CGEventType(rawValue: 7) { // Assuming 7 is the custom event type for window info
        if let activeWindowInfo = getActiveWindowInfo() {
            let windowInfoString = "WINDOW_INFO,ACTIVE,\(activeWindowInfo.jsonString ?? "{}")"
            curId = curId + 1
            print("\(windowInfoString),\(curId)")
            fflush(stdout)
        }

        let allWindowsInfo = getAllWindows()
        let allWindowsInfoString = "WINDOW_INFO,ALL,\(allWindowsInfo.jsonString ?? "[]")"
        curId = curId + 1
        print("\(allWindowsInfoString),\(curId)")
        fflush(stdout)

        return nil // Don't propagate custom events
    }

    if [.keyDown, .keyUp].contains(type) {
        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
        let flags = getModifierFlags(event: event)

        // Get the character string from the NSEvent
        if let nsEvent = NSEvent(cgEvent: event) {
            // Handle special keys
            if let specialKey = nsEvent.specialKey {
                // Send special key name instead of character
                curId = curId + 1
                print("SPECIAL_KEY,\(type == .keyDown ? "DOWN" : "UP"),\(specialKey),\(event.location.x),\(event.location.y),\(curId),\(flags)")
                fflush(stdout)
            } else if let characters = nsEvent.characters {
                for character in characters {
                    let characterString = String(character)
                    curId = curId + 1
                    print("CHARACTER,\(type == .keyDown ? "DOWN" : "UP"),\(characterString),\(event.location.x),\(event.location.y),\(curId),\(flags)")
                    fflush(stdout)
                }
            }
        }
        
    } else if [.flagsChanged].contains(type) {
        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
        let downState = getModifierDownState(event: event, keyCode: keyCode)
        let modifierFlags = getModifierFlags(event: event)

        // Send a MODIFIER event
        curId = curId + 1
        print("MODIFIER,\(keyCode),\(downState ? "DOWN" : "UP"),\(event.location.x),\(event.location.y),\(curId),\(modifierFlags)")
        fflush(stdout)

    } else if [
        .leftMouseDown,
        .leftMouseUp,
        .rightMouseDown,
        .rightMouseUp,
        .otherMouseDown,
        .otherMouseUp,
    ].contains(type) {
        let isDown = [
            .leftMouseDown,
            .rightMouseDown,
            .otherMouseDown,
        ].contains(type)
        let keyCode = event.getIntegerValueField(.mouseEventButtonNumber)
        _ = haltPropogation(
            isMouse: true,
            isDown: isDown,
            keyCode: keyCode,
            location: (event.location.x, event.location.y)
        )

    } else if type == .mouseMoved {
        curId = curId + 1
        print("MOUSE,MOVE,\(event.location.x),\(event.location.y),\(curId)")
        fflush(stdout)
    } else if type == .scrollWheel {
        let scrollDelta = event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
        curId = curId + 1
        print("MOUSE,SCROLL,\(scrollDelta),\(event.location.x),\(event.location.y),\(curId)")
        fflush(stdout)
    } else if type == CGEventType.tapDisabledByTimeout {
        logErr("Timeout error raised on key listener")
        return nil
    }
    return Unmanaged.passUnretained(event)
}

//Define an event mask to quickly narrow down to the events we desire to capture
let keyEventMask =
    (1 << CGEventType.flagsChanged.rawValue)
    | (1 << CGEventType.keyDown.rawValue)
    | (1 << CGEventType.keyUp.rawValue)

let mouseEventMask =
    (1 << CGEventType.leftMouseDown.rawValue)
    | (1 << CGEventType.leftMouseUp.rawValue)
    | (1 << CGEventType.rightMouseDown.rawValue)
    | (1 << CGEventType.rightMouseUp.rawValue)
    | (1 << CGEventType.otherMouseDown.rawValue)
    | (1 << CGEventType.otherMouseUp.rawValue)
    | (1 << CGEventType.mouseMoved.rawValue)
    | (1 << CGEventType.scrollWheel.rawValue)

let eventMask =
    keyEventMask
    | mouseEventMask
    | (1 << CGEventType(rawValue: 7).rawValue)

// Set up workspace notification observer before event loop
NSWorkspace.shared.notificationCenter.addObserver(
    forName: NSWorkspace.didActivateApplicationNotification,
    object: nil,
    queue: nil
) { notification in
    let appName = getActiveAppName()
    curId = curId + 1
    // Emit an application change event
    print("APPLICATION,\(appName),\(curId)")
    fflush(stdout)
}

//Create the event tap using [CGEvent.tapCreate](https://developer.apple.com/documentation/coregraphics/cgevent/1454426-tapcreate)
guard
    let eventTap = CGEvent.tapCreate(
        tap: .cgSessionEventTap,
        place: .headInsertEventTap,
        options: .defaultTap,
        eventsOfInterest: CGEventMask(eventMask),
        callback: myCGEventTapCallback,
        userInfo: nil
    )
else {
    logErr(
        "Failed to create event tap. This may be because the application this is embedded within hasn't received permission. Please go to System Preferences > Security > Accesibility to add this application to the trusted applications."
    )
    exit(1)
}

// Timer for window info broadcasting
let windowInfoTimer = DispatchSource.makeTimerSource(flags: [], queue: DispatchQueue.global(qos: .background))
windowInfoTimer.schedule(deadline: .now(), repeating: .seconds(10)) // Adjust the interval as needed
windowInfoTimer.setEventHandler {
    // Post a custom event to trigger window info output
    if let event = CGEvent(source: nil) {
        event.type = CGEventType(rawValue: 7) // Use our custom event type
        event.post(tap: .cgSessionEventTap)
    }
}
windowInfoTimer.resume()

//Launch threads for timeout system
let inputThread = DispatchQueue(label: "Input thread")
inputThread.async {
    checkInputLoop()
}
let timeoutThread = DispatchQueue(label: "Timeout thread")
timeoutThread.async {
    timeoutLoop()
}

//Enable tab and run event loop.
let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, eventTap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
CGEvent.tapEnable(tap: eventTap, enable: true)
CFRunLoopRun()  //Note: This is a blocking call
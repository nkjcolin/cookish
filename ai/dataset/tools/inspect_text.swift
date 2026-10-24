// Read-only local OCR to assist checking the generated receipt text. No API calls.
import Foundation
import Vision

var results: [[String: Any]] = []
for path in CommandLine.arguments.dropFirst() {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    do {
        try VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:]).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        results.append(["image": path, "lines": lines])
    } catch {
        results.append(["image": path, "error": String(describing: error)])
    }
}
let data = try JSONSerialization.data(withJSONObject: results, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)

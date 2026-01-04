import React, { useState } from "react";
import "./App.css";

function App() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  // Handle file selection
  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files);
    setFiles((prev) => {
      const allFiles = [...prev];
      newFiles.forEach((file) => {
        if (!allFiles.some((f) => f.name === file.name)) {
          allFiles.push(file);
        }
      });
      return allFiles;
    });
    e.target.value = null; // allow re-selecting same file
  };

  // Remove a file
  const handleRemoveFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Submit to Lambda
const MAX_FILE_SIZE_MB = 5; // Max 5 MB per file
const MAX_TOTAL_SIZE_MB = 10; // Max 10 MB total for all files

const handleSubmit = async (e) => {
  e.preventDefault();
  if (files.length === 0) return alert("Please select at least one file!");
  setLoading(true);

  try {
    // Check file sizes
    let totalSize = 0;
    for (const file of files) {
      totalSize += file.size;
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        alert(`File "${file.name}" exceeds ${MAX_FILE_SIZE_MB} MB limit.`);
        setLoading(false);
        return;
      }
    }
    if (totalSize > MAX_TOTAL_SIZE_MB * 1024 * 1024) {
      alert(`Total files exceed ${MAX_TOTAL_SIZE_MB} MB limit.`);
      setLoading(false);
      return;
    }

    // Convert files to base64
    const filesData = await Promise.all(
      files.map(
        (file) =>
          new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const base64 = reader.result.split(",")[1]; // remove prefix
              resolve({ filename: file.name, content: base64 });
            };
            reader.onerror = (err) => reject(err);
            reader.readAsDataURL(file);
          })
      )
    );

    // Send POST request
    const res = await fetch(
      "",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: filesData }),
      }
    );

    if (!res.ok) {
      // Try to read JSON or raw text for error
      let errorText = "";
      try {
        const errJson = await res.json();
        errorText = errJson.error || JSON.stringify(errJson);
      } catch {
        errorText = await res.text();
      }
      console.error("Backend error:", errorText);
      alert("Error: " + (errorText || "Processing failed"));
      setLoading(false);
      return;
    }

    // Receive PDF blob
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "cleaned_output.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (ex) {
    console.error("Client error:", ex);
    alert("Failed to connect to backend");
  } finally {
    setLoading(false);
  }
};


  return (
    <div className="container">
      <div className="card">
        <h2>File Cleaner</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="file"
            multiple
            onChange={handleFileChange}
            accept=".txt,.pdf,.docx,.pptx"
            className="file-input"
          />

          {files.length > 0 && (
            <ul className="file-list">
              {files.map((f, idx) => (
                <li key={idx}>
                  {f.name}{" "}
                  <button type="button" onClick={() => handleRemoveFile(idx)}>
                    ❌
                  </button>
                </li>
              ))}
            </ul>
          )}

          <button type="submit" disabled={loading} className="submit-btn">
            {loading ? "Cleaning..." : "Upload & Clean"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;


import React, { useState } from "react";
import "./App.css"; // ✅ Make sure this file exists in src/

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (e) => setFile(e.target.files[0]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return alert("Please select a file!");
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/clean-file", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert("Error: " + (err.error || "Processing failed"));
        setLoading(false);
        return;
      }

      // const blob = await res.blob();
      // const url = window.URL.createObjectURL(blob);
      // const a = document.createElement("a");
      // a.href = url;
      // a.download = `cleaned_${file.name.replace(/\.[^/.]+$/, "")}.pdf`;
      // document.body.appendChild(a);
      // a.click();
      // a.remove();
      // window.URL.revokeObjectURL(url);
      const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);

        // ✅ Try to extract filename from backend header
        const contentDisposition = res.headers.get("content-disposition");
        let filename = `cleaned_${file.name.replace(/\.[^/.]+$/, "")}`;

        if (contentDisposition) {
          const match = contentDisposition.match(/filename="?([^"]+)"?/);
          if (match) {
            filename = match[1];
          }
        }

        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (ex) {
      console.error(ex);
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
            onChange={handleFileChange}
            accept=".txt,.pdf,.docx,.pptx"
            className="file-input"
          />

          <button type="submit" disabled={loading} className="submit-btn">
            {loading ? "Cleaning..." : "Upload & Clean"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;

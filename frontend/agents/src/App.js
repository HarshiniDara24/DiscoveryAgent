
// import React, { useState } from "react";
// import "./App.css"; // ✅ Make sure this file exists in src/

// function App() {
//   const [file, setFile] = useState(null);
//   const [loading, setLoading] = useState(false);

//   const handleFileChange = (e) => setFile(e.target.files[0]);

//   const handleSubmit = async (e) => {
//     e.preventDefault();
//     if (!file) return alert("Please select a file!");
//     setLoading(true);

//     const formData = new FormData();
//     formData.append("file", file);

//     try {
//       const res = await fetch("http://127.0.0.1:8000/clean-file", {
//         method: "POST",
//         body: formData
//       });

//       if (!res.ok) {
//         const err = await res.json().catch(() => ({}));
//         alert("Error: " + (err.error || "Processing failed"));
//         setLoading(false);
//         return;
//       }

//       // const blob = await res.blob();
//       // const url = window.URL.createObjectURL(blob);
//       // const a = document.createElement("a");
//       // a.href = url;
//       // a.download = `cleaned_${file.name.replace(/\.[^/.]+$/, "")}.pdf`;
//       // document.body.appendChild(a);
//       // a.click();
//       // a.remove();
//       // window.URL.revokeObjectURL(url);
//       const blob = await res.blob();
//         const url = window.URL.createObjectURL(blob);

//         // ✅ Try to extract filename from backend header
//         const contentDisposition = res.headers.get("content-disposition");
//         let filename = `cleaned_${file.name.replace(/\.[^/.]+$/, "")}`;

//         if (contentDisposition) {
//           const match = contentDisposition.match(/filename="?([^"]+)"?/);
//           if (match) {
//             filename = match[1];
//           }
//         }

//         const a = document.createElement("a");
//         a.href = url;
//         a.download = filename;
//         document.body.appendChild(a);
//         a.click();
//         a.remove();
//         window.URL.revokeObjectURL(url);

//     } catch (ex) {
//       console.error(ex);
//       alert("Failed to connect to backend");
//     } finally {
//       setLoading(false);
//     }
//   };

//   return (
//     <div className="container">
//       <div className="card">
//         <h2>File Cleaner</h2>
//         <form onSubmit={handleSubmit}>
//           <input
//             type="file"
//             onChange={handleFileChange}
//             accept=".txt,.pdf,.docx,.pptx"
//             className="file-input"
//           />

//           <button type="submit" disabled={loading} className="submit-btn">
//             {loading ? "Cleaning..." : "Upload & Clean"}
//           </button>
//         </form>
//       </div>
//     </div>
//   );
// }

// export default App;


import React, { useState } from "react";
import "./App.css"; // ✅ Make sure this file exists in src/

function App() {
  // const [file, setFile] = useState(null);
  const [files, setFiles] = useState([]);

  const [loading, setLoading] = useState(false);

 // const handleFileChange = (e) => setFile(e.target.files[0]);
 //const handleFileChange = (e) => setFiles([...e.target.files]);
 const handleFileChange = (e) => {
  const newFiles = Array.from(e.target.files);
  setFiles((prevFiles) => {
    // Avoid duplicates by filename
    const allFiles = [...prevFiles];
    newFiles.forEach((file) => {
      if (!allFiles.some((f) => f.name === file.name)) {
        allFiles.push(file);
      }
    });
    return allFiles;
  });

  // Reset input so same file can be selected again if needed
  e.target.value = null;
};



  const handleSubmit = async (e) => {
    e.preventDefault();
    // if (!file) return alert("Please select a file!");
    if (files.length === 0) return alert("Please select at least one file!");
    setLoading(true);

    const formData = new FormData();
    //formData.append("file", file);
    files.forEach((f) => formData.append("files", f));


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
        // let filename = `cleaned_${file.name.replace(/\.[^/.]+$/, "")}`;
        let filename = "cleaned_output.pdf";


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
            multiple
            onChange={handleFileChange}
            accept=".txt,.pdf,.docx,.pptx"
            className="file-input"
          />
          
            {/* Display selected files */}
              {files.length > 0 && (
                <ul className="file-list">
                  {files.map((f, idx) => (
                    <li key={idx}>{f.name}</li>
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

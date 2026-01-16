'use client';
import { useState, useEffect } from 'react';
import { renameFile } from '../services/api';
import './App.css';

// File validation constants
const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpg', 'image/jpeg'];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const FILE_TYPE_LABELS = [
    { type: 'application/pdf', label: 'PDF' },
    { type: 'image/png', label: 'PNG' },
    { type: 'image/jpeg', label: 'JPG' },
];

// Simple SVG Icons
const ArrowRight = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="arrow-icon">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
);

// Dynamic File Icons - Monochromatic Theme
const PdfIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.9 }}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
);

const ImageIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.9 }}>
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <polyline points="21 15 16 10 5 21"></polyline>
    </svg>
);

const DefaultFileIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
        <polyline points="13 2 13 9 20 9"></polyline>
    </svg>
);

const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    if (ext === 'pdf') return <PdfIcon />;
    if (['png', 'jpg', 'jpeg'].includes(ext)) return <ImageIcon />;
    return <DefaultFileIcon />;
};

const FileCard = ({ file, index }) => {
    const [loadingText, setLoadingText] = useState('Uploading...');

    useEffect(() => {
        if (file.status === 'processing') {
            const timers = [];
            // Randomize timings to feel more organic
            const baseDelay = Math.random() * 500;
            const step1 = 800 + Math.random() * 600;
            const step2 = step1 + 1000 + Math.random() * 800;
            const step3 = step2 + 1200 + Math.random() * 800;
            const step4 = step3 + 1500;

            timers.push(setTimeout(() => setLoadingText('Reading file...'), baseDelay + step1));
            timers.push(setTimeout(() => setLoadingText('Extracting text...'), baseDelay + step2));
            timers.push(setTimeout(() => setLoadingText('Analyzing content...'), baseDelay + step3));
            timers.push(setTimeout(() => setLoadingText('Renaming...'), baseDelay + step4));

            return () => timers.forEach(clearTimeout);
        } else {
            setLoadingText('Uploading...'); // Reset
        }
    }, [file.status]);

    if (file.status === 'done') return null;

    // Determine Extra Classes
    let extraClass = '';
    if (file.status === 'processing') extraClass = 'processing-state';
    if (file.status === 'exiting') extraClass = 'exiting';
    if (file.status === 'error') extraClass = 'error-state';

    return (
        <div
            className={`file-card ${extraClass}`}
            style={{
                '--delay': `${index * 100}ms`,
                ...(file.status === 'error' ? { borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)' } : {})
            }}
        >
            {getFileIcon(file.originalName)}
            <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1 }}>
                <span className="filename" style={{ color: file.status === 'error' ? '#fca5a5' : 'inherit' }}>{file.originalName}</span>

                {/* Error Message */}
                {file.status === 'error' && (
                    <span style={{ fontSize: '0.75rem', color: '#ef4444', marginTop: '0.2rem' }}>
                        {file.errorMsg}
                    </span>
                )}

                {/* Loading Animation Text */}
                {file.status === 'processing' && (
                    <span className="loading-text">
                        {loadingText}
                    </span>
                )}
            </div>
            {/* Spinner or visual indicator can go here if needed, but text is dynamic enough */}
        </div>
    );
};

export default function Home() {
    const [files, setFiles] = useState([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const validateFiles = (selectedFiles) => {
        setErrorMessage(null); // Clear previous errors

        const rejectedFiles = [];
        const validFiles = selectedFiles.filter(file => {
            // Check file type
            if (!ALLOWED_TYPES.includes(file.type)) {
                rejectedFiles.push(`${file.name}: Unsupported file type`);
                return false;
            }
            // Check file size
            if (file.size > MAX_FILE_SIZE) {
                rejectedFiles.push(`${file.name}: File exceeds 5MB limit`);
                return false;
            }
            return true;
        });

        if (rejectedFiles.length > 0) {
            setErrorMessage(`Rejected: ${rejectedFiles[0]}` + (rejectedFiles.length > 1 ? ` (+${rejectedFiles.length - 1} more)` : ''));
            return [];
        }

        return validFiles;
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            processFiles(Array.from(e.dataTransfer.files));
        }
    };


    const handleFileUpload = (e) => {
        const selectedFiles = Array.from(e.target.files);
        if (selectedFiles.length === 0) return;
        processFiles(selectedFiles);
        // Reset input value to allow re-selecting same files
        e.target.value = '';
    };

    const processFiles = (selectedFiles) => {
        const validFiles = validateFiles(selectedFiles);
        if (validFiles.length === 0) return;

        // Count current idle files
        const currentIdleCount = files.filter(f => f.status === 'idle').length;
        const availableSlots = 3 - currentIdleCount;

        if (availableSlots <= 0) {
            setErrorMessage('Maximum 3 files allowed. Please process current files first.');
            return;
        }

        // Only take as many files as we have slots for
        const filesToAdd = validFiles.slice(0, availableSlots);

        if (filesToAdd.length < validFiles.length) {
            setErrorMessage(`Only ${availableSlots} slot(s) available. Added ${filesToAdd.length} of ${validFiles.length}.`);
        }

        const newFiles = filesToAdd.map((file, index) => ({
            id: Date.now() + index,
            originalName: file.name,
            fileObj: file,
            newName: null,
            status: 'idle',
        }));

        // Prepend new files to the "top" (start of array) so they appear visually at the top
        setFiles(prev => [...newFiles, ...prev]);
    };



    // Download a single file
    const downloadFile = (file) => {
        if (!file.blob || !file.newName) return;
        const url = window.URL.createObjectURL(file.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.newName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    };

    // Download all completed files
    const downloadAll = () => {
        const doneFiles = files.filter(f => f.status === 'done' && f.blob);
        doneFiles.forEach((file, index) => {
            // Stagger downloads to prevent browser blocking
            setTimeout(() => downloadFile(file), index * 200);
        });
    };

    // Process all files in parallel - first to complete appears first
    const processAllFiles = async () => {
        if (isProcessing) return;
        setIsProcessing(true);

        // Get all idle files
        const idleFiles = files.filter(f => f.status === 'idle');

        if (idleFiles.length === 0) {
            setIsProcessing(false);
            return;
        }

        // Mark all as processing
        setFiles(currentFiles =>
            currentFiles.map(f =>
                f.status === 'idle' ? { ...f, status: 'processing' } : f
            )
        );

        // Process all files in parallel
        const promises = idleFiles.map(file =>
            renameFile(file.fileObj)
                .then(({ blob, filename }) => {
                    // Update UI - first to 'exiting', then to 'done'
                    setFiles(currentFiles => {
                        const idx = currentFiles.findIndex(f => f.id === file.id);
                        if (idx === -1) return currentFiles;

                        const updatedFiles = [...currentFiles];
                        updatedFiles[idx] = { ...updatedFiles[idx], status: 'exiting' };
                        return updatedFiles;
                    });

                    // After animation, mark as done
                    setTimeout(() => {
                        setFiles(currentFiles => {
                            const idx = currentFiles.findIndex(f => f.id === file.id);
                            if (idx === -1) return currentFiles;

                            const updatedFiles = [...currentFiles];
                            updatedFiles[idx] = {
                                ...updatedFiles[idx],
                                status: 'done',
                                newName: filename,
                                blob: blob
                            };
                            return updatedFiles;
                        });
                    }, 500);

                    return { success: true, id: file.id };
                })
                .catch(err => {
                    console.error('Rename failed for', file.originalName, err);

                    setFiles(currentFiles => {
                        const idx = currentFiles.findIndex(f => f.id === file.id);
                        if (idx === -1) return currentFiles;

                        const updatedFiles = [...currentFiles];
                        updatedFiles[idx] = {
                            ...updatedFiles[idx],
                            status: 'error',
                            errorMsg: err.message
                        };
                        return updatedFiles;
                    });

                    return { success: false, id: file.id, error: err.message };
                })
        );

        // Wait for all to complete
        await Promise.allSettled(promises);
        setIsProcessing(false);
    };


    return (
        <div className="app-container">
            <header className="header">
                <h1>AI Files Renamer</h1>
                <p>Upload documents and images, get meaningful filenames in seconds.</p>
            </header>

            <main className="stage">
                {/* Left Zone: Input */}
                <div className="zone input-zone">
                    <div className="zone-title">Input Files</div>

                    <div className="file-list">
                        {errorMessage && (
                            <div className="error-banner">
                                {errorMessage}
                                <button onClick={() => setErrorMessage(null)} className="close-error">×</button>
                            </div>
                        )}
                        {/* Drop zone - Always rendered but collapsed when files exist */}
                        <label
                            className={`file-input-wrapper ${files.filter(f => f.status === 'idle' || f.status === 'processing' || f.status === 'exiting').length > 0 ? 'collapsed' : ''} ${dragActive ? 'drag-active' : ''}`}
                            onDragEnter={handleDrag}
                            onDragLeave={handleDrag}
                            onDragOver={handleDrag}
                            onDrop={handleDrop}
                        >
                            <input
                                type="file"
                                multiple
                                accept=".pdf,.png,.jpg,.jpeg"
                                onChange={handleFileUpload}
                                className="hidden-input"
                            />
                            <div className="drop-zone-content">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="drop-icon">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                    <polyline points="17 8 12 3 7 8"></polyline>
                                    <line x1="12" y1="3" x2="12" y2="15"></line>
                                </svg>
                                <span className="drop-text">Drop your files here</span>
                                <span className="drop-subtext">or click to browse</span>
                                <div className="file-type-badges">
                                    {FILE_TYPE_LABELS.map(ft => (
                                        <span key={ft.type} className="file-type-badge">{ft.label}</span>
                                    ))}
                                </div>
                                <span className="size-limit">Max 5MB per file</span>
                            </div>
                        </label>

                        {/* Render Idle/Processing files */}
                        {files.map((file, index) => (
                            <FileCard key={file.id} file={file} index={index} />
                        ))}
                        {/* Show "Add more files" when less than 3 idle files and not processing */}
                        {files.filter(f => f.status === 'idle').length < 3 && !isProcessing && (
                            <label className="add-more-btn" style={{ marginTop: '1rem', textAlign: 'center', display: 'block', cursor: 'pointer', color: 'var(--text-muted)' }}>
                                <input type="file" multiple onChange={handleFileUpload} className="hidden-input" />
                                <small>+ Add more files ({3 - files.filter(f => f.status === 'idle').length} slots left)</small>
                            </label>
                        )}
                    </div>
                </div>

                {/* Transition Zone */}
                <div className="transition-area">
                    <button
                        className="arrow-btn"
                        onClick={processAllFiles}
                        disabled={isProcessing || !files.some(f => f.status === 'idle')}
                    >
                        <ArrowRight />
                        <span className="rename-text">{isProcessing ? 'IGNITING...' : 'RENAME'}</span>
                    </button>
                </div>

                {/* Right Zone: Output */}
                <div className="zone output-zone">
                    <div className="zone-title">Renamed Files</div>
                    <div className="file-list">
                        {/* Render "Done" files in REVERSE order. 
                 Newest result (just finished) should be at the BOTTOM (pushes others up). 
                 Wait, if we use flex-direction: column (standard), items render Top -> Bottom.
                 If we want the NEWEST item to appear at the bottom, we should render it LAST.
                 Our `files` array has [NewestInput, ..., OldestInput].
                 When OldestInput finishes, it becomes NewestOutput.
                 So we want to render the FINISHED files such that the most recently finished is at the bottom.
                 
                 If we filter: files.filter(done).
                 If files = [C(idle), B(done), A(done)].
                 A finished first. B finished second.
                 We want A (Top) -> B (Bottom).
                 If we filter: [B, A].
                 To get [A, B], we must REVERSE the filtered list.
             */}
                        {files
                            .filter(f => f.status === 'done')
                            .reverse()
                            .map(file => (
                                <div key={file.id} className="file-card result-card bounce-in">
                                    {getFileIcon(file.originalName)}
                                    <div className="result-info">
                                        <span className="filename success">{file.newName}</span>
                                        <span className="original-name">{file.originalName}</span>
                                    </div>
                                </div>
                            ))
                        }
                    </div>
                    {/* Download All Button - Count Badge */}
                    {files.filter(f => f.status === 'done').length > 0 && (
                        <button
                            className="download-btn"
                            title="Download All"
                            onClick={downloadAll}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            <span className="badge">{files.filter(f => f.status === 'done').length}</span>
                        </button>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
}

const Footer = () => {
    const techStack = [
        { title: "FRONTEND", name: "Next.js & React", link: "https://nextjs.org/docs" },
        { title: "BACKEND", name: "FastAPI (Python)", link: "https://fastapi.tiangolo.com/" },
        { title: "INFRASTRUCTURE", name: "Docker & AWS", link: "https://docs.docker.com/" },
        { title: "LLM OPS", name: "Langfuse", link: "https://langfuse.com/" },
    ];

    return (
        <footer className="footer">
            <div className="tech-grid">
                {techStack.map((tech, index) => (
                    <a key={index} href={tech.link} target="_blank" rel="noopener noreferrer" className="tech-card">
                        <span className="tech-title">{tech.title}</span>
                        <span className="tech-name">{tech.name}</span>
                    </a>
                ))}
            </div>
            <div className="copyright">
                <a href="https://github.com/Hj-lh/ArabicFile-Renamer" target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
                    </svg>
                    © 2026 Abdullah Alhajlah
                </a>
            </div>
        </footer>
    );
};

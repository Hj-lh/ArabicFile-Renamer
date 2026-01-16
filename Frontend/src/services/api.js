const API_URL = '/api/proxy';

export const renameFile = async (file, instruction) => {
    const formData = new FormData();
    formData.append('files', file);

    // Note: 'instruction' is not currently used by the new backend /upload endpoint
    // based on the provided documentation, but we keep the argument for compatibility.

    const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
        headers: {
            'Connection': 'keep-alive',
        },
    });

    if (!response.ok) {
        // Handle Rate Limit specifically if possible
        if (response.status === 429) {
            const text = await response.text();
            let msg = 'Daily limit reached';
            try {
                const json = JSON.parse(text);
                if (json.error) msg = json.error;
            } catch (e) { }
            throw new Error(msg);
        }
        throw new Error(`Upload failed: ${response.statusText}`);
    }

    if (!response.body) {
        throw new Error('No response body from server');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let newFilename = null;
    let error = null;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.trim().startsWith('data: ')) {
                    try {
                        const jsonStr = line.trim().slice(6);
                        const event = JSON.parse(jsonStr);

                        if (event.type === 'result' && event.data) {
                            if (event.data.status === 'success') {
                                newFilename = event.data.new_filename;
                            } else if (event.data.status === 'error') {
                                error = event.data.error || 'Unknown error from AI';
                            }
                        } else if (event.type === 'error') {
                            error = event.error || 'Unknown error event';
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE line:', line, e);
                    }
                }
            }
        }
    } catch (err) {
        console.error('Stream reading error:', err);
        throw err;
    }

    if (error) {
        throw new Error(error);
    }

    if (!newFilename) {
        throw new Error('AI did not return a new filename');
    }

    // Return the original blob and the new filename, matching existing UI expectations
    return { blob: file, filename: newFilename };
};

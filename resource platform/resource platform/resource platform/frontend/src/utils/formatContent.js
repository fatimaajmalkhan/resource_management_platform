// Formatter to render markdown list items, bold texts, and blocks correctly.
// Shared between the full ChatArea and the FloatingAssistant widget.
export function formatContent(text) {
    if (!text) return '';

    // Escape standard HTML chars to prevent XSS
    let formatted = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Replace bold syntax **text** with <strong>text</strong>
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Replace `code` syntax with <code>code</code>
    formatted = formatted.replace(/`(.*?)`/g, '<code>$1</code>');

    // Convert list items
    const lines = formatted.split('\n');
    let inList = false;
    const processedLines = [];

    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            if (!inList) {
                processedLines.push('<ul>');
                inList = true;
            }
            processedLines.push(`<li>${trimmed.substring(2)}</li>`);
        } else {
            if (inList) {
                processedLines.push('</ul>');
                inList = false;
            }
            processedLines.push(line);
        }
    }
    if (inList) {
        processedLines.push('</ul>');
    }

    return processedLines.join('<br>').replace(/<\/ul><br>/g, '</ul>').replace(/<ul><br>/g, '<ul>');
}

function exportAndShare(profileId, year, month) {
    fetch(`/api/export-pdf/${profileId}/${year}/${month}/`)
        .then(res => {
            if (!res.ok) throw new Error('Export failed');
            return res.json();
        })
        .then(data => {
            // Decode base64 to blob
            const byteCharacters = atob(data.pdf_base64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'application/pdf' });

            // Try Web Share API with file (mobile)
            if (navigator.canShare && navigator.canShare({ files: [new File([blob], data.filename, { type: 'application/pdf' })] })) {
                navigator.share({
                    files: [new File([blob], data.filename, { type: 'application/pdf' })],
                    title: data.filename,
                }).catch(err => {
                    console.warn('Share cancelled or failed', err);
                    const url = URL.createObjectURL(blob);
                    window.open(url, '_blank');
                });
            } else if (navigator.share) {
                // Share without file (some browsers)
                const url = URL.createObjectURL(blob);
                navigator.share({ url }).catch(() => {
                    window.open(url, '_blank');
                });
            } else {
                // Desktop fallback
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
            }
        })
        .catch(err => {
            console.error('PDF export error:', err);
            alert('PDF export failed. Please try again.');
        });
}

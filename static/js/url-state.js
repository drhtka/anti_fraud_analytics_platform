function buildUrlWithLanguage(targetLanguage, baseUrl = window.location.href) {
    const nextUrl = new URL(baseUrl, window.location.origin);
    nextUrl.searchParams.set('lang', targetLanguage);
    return nextUrl;
}

export { buildUrlWithLanguage };

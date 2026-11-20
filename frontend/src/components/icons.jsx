const S = ({ children, size = 17 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

export const IconPlay = (p) => (
  <S {...p}><polygon points="8 5 19 12 8 19 8 5" fill="currentColor" stroke="none" /></S>
);
export const IconHome = (p) => (
  <S {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></S>
);
export const IconFilm = (p) => (
  <S {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4" /></S>
);
export const IconScissors = (p) => (
  <S {...p}><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><path d="M8.1 7.6 20 19M8.1 16.4 20 5" /></S>
);
export const IconUpload = (p) => (
  <S {...p}><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></S>
);
export const IconClipboard = (p) => (
  <S {...p}><rect x="7" y="4" width="10" height="16" rx="2" /><path d="M10 4.5h4" /></S>
);
export const IconSpark = (p) => (
  <S {...p}><path d="M12 3l1.9 5.4L19 10l-5.1 1.6L12 17l-1.9-5.4L5 10l5.1-1.6L12 3z" fill="currentColor" stroke="none" /></S>
);
export const IconChart = (p) => (
  <S {...p}><path d="M4 20V6M4 20h16" /><path d="M8 16v-4M12 16V8M16 16v-6" /></S>
);
export const IconRefresh = (p) => (
  <S {...p}><path d="M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3" /><path d="M20 4v4h-4M4 20v-4h4" /></S>
);
export const IconDownload = (p) => (
  <S {...p}><path d="M12 4v12m0 0 4-4m-4 4-4-4" /><path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" /></S>
);
export const IconTrash = (p) => (
  <S {...p}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></S>
);
export const IconBack = (p) => (
  <S {...p}><path d="M15 5l-7 7 7 7" /></S>
);
export const IconDot = (p) => (
  <S {...p}><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" /></S>
);

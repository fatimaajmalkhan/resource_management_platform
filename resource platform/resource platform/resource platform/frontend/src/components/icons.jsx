import React from 'react';

// Shared line-icon set. All icons inherit `currentColor` and a 1.5px stroke so
// they read as one system and pick up hover/active text colors automatically.
const base = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.5,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
};

export function IconOverview(props) {
    return (
        <svg {...base} {...props}>
            <rect x="4" y="4" width="7" height="9" rx="1.5" />
            <rect x="4" y="16" width="7" height="4" rx="1.5" />
            <rect x="14" y="4" width="6" height="4" rx="1.5" />
            <rect x="14" y="11" width="6" height="9" rx="1.5" />
        </svg>
    );
}

export function IconAssistant(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9A1.5 1.5 0 0 1 18.5 16H9l-4 4v-4H5.5A1.5 1.5 0 0 1 4 14.5z" />
            <path d="M8.5 9.5h7M8.5 12h4" />
        </svg>
    );
}

export function IconFunnel(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 5h16l-6 7v6l-4 2v-8z" />
        </svg>
    );
}

export function IconResources(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
        </svg>
    );
}

export function IconPlus(props) {
    return (
        <svg {...base} {...props}>
            <path d="M12 5v14M5 12h14" />
        </svg>
    );
}

export function IconChat(props) {
    return (
        <svg {...base} {...props}>
            <path d="M5 5.5A1.5 1.5 0 0 1 6.5 4h11A1.5 1.5 0 0 1 19 5.5v8A1.5 1.5 0 0 1 17.5 15H10l-4 4v-4h.5A1.5 1.5 0 0 1 5 13.5z" />
        </svg>
    );
}

export function IconTrash(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
        </svg>
    );
}

export function IconPractice(props) {
    return (
        <svg {...base} {...props}>
            <path d="M5 20V10M12 20V5M19 20v-7" />
        </svg>
    );
}

export function IconEmail(props) {
    return (
        <svg {...base} {...props}>
            <rect x="3.5" y="5.5" width="17" height="13" rx="1.5" />
            <path d="M4 7l8 6 8-6" />
        </svg>
    );
}

export function IconFlag(props) {
    return (
        <svg {...base} {...props}>
            <path d="M6 21V4M6 4h11l-2 4 2 4H6" />
        </svg>
    );
}

export function IconHistory(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 12a8 8 0 1 0 2.5-5.8M4 4v3h3" />
            <path d="M12 8v4l3 2" />
        </svg>
    );
}

export function IconPin(props) {
    return (
        <svg {...base} {...props}>
            <path d="M12 21s6-5.3 6-10a6 6 0 1 0-12 0c0 4.7 6 10 6 10z" />
            <circle cx="12" cy="11" r="2" />
        </svg>
    );
}

export function IconCalendar(props) {
    return (
        <svg {...base} {...props}>
            <rect x="4" y="5" width="16" height="16" rx="2" />
            <path d="M4 9h16M8 3v4M16 3v4" />
        </svg>
    );
}

export function IconBriefcase(props) {
    return (
        <svg {...base} {...props}>
            <rect x="3" y="7" width="18" height="13" rx="2" />
            <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
        </svg>
    );
}

export function IconUser(props) {
    return (
        <svg {...base} {...props}>
            <circle cx="12" cy="8" r="3.5" />
            <path d="M5 20a7 7 0 0 1 14 0" />
        </svg>
    );
}

export function IconCheck(props) {
    return (
        <svg {...base} {...props}>
            <path d="M20 6L9 17l-5-5" />
        </svg>
    );
}

export function IconAlert(props) {
    return (
        <svg {...base} {...props}>
            <path d="M12 3l9 16H3z" />
            <path d="M12 10v4M12 17h.01" />
        </svg>
    );
}

export function IconEdit(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 20h4L18.5 9.5a2 2 0 0 0-3-3L5 17z" />
            <path d="M13.5 6.5l3 3" />
        </svg>
    );
}

export function IconSend(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 12l16-7-7 16-2.5-6.5z" />
        </svg>
    );
}

export function IconClose(props) {
    return (
        <svg {...base} {...props}>
            <path d="M6 6l12 12M18 6L6 18" />
        </svg>
    );
}

export function IconTrendUp(props) {
    return (
        <svg {...base} {...props}>
            <path d="M4 17l6-6 4 4 6-8" />
            <path d="M14 7h6v6" />
        </svg>
    );
}

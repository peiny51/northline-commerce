/** Format prices stored in integer cents (all shop prices are CAD). */
export function money(cents) {
    return `$${(cents / 100).toFixed(2)} CAD`;
}
export function placeholder(name) {
    return `https://placehold.co/600x720/e7e9e7/3b4b40?text=${encodeURIComponent(name)}`;
}

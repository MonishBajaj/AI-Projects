// utils.js
// Mathematical helper utilities
// Export a single object MathHelpers containing all functions and constants.
// No external dependencies; uses native Math.

// Internal cache for factorial results to improve performance.
const factorialCache = new Map();
// Seed cache with 0! = 1
factorialCache.set(0, 1);

/**
 * Compute factorial of a non‑negative integer n.
 * Uses memoization for speed.
 * @param {number} n
 * @returns {number}
 * @throws {TypeError|RangeError} if n is not a non‑negative integer.
 */
function factorial(n) {
  if (typeof n !== 'number' || !Number.isFinite(n)) {
    throw new TypeError('factorial: argument must be a finite number');
  }
  if (!Number.isInteger(n)) {
    throw new RangeError('factorial: argument must be an integer');
  }
  if (n < 0) {
    throw new RangeError('factorial: argument must be non‑negative');
  }
  if (factorialCache.has(n)) {
    return factorialCache.get(n);
  }
  // compute iteratively to avoid call‑stack limits
  let result = 1;
  // start from the largest cached value less than n
  for (let i = n; i > 0; i--) {
    if (factorialCache.has(i)) {
      result = factorialCache.get(i);
      for (let j = i + 1; j <= n; j++) {
        result *= j;
      }
      factorialCache.set(n, result);
      return result;
    }
  }
  // fallback: compute from 1
  result = 1;
  for (let i = 2; i <= n; i++) {
    result *= i;
  }
  factorialCache.set(n, result);
  return result;
}

// Helper to multiply numbers in a range (inclusive). Used internally.
function productRange(start, end) {
  let prod = 1;
  for (let i = start; i <= end; i++) {
    prod *= i;
  }
  return prod;
}

/**
 * Power function.
 * @param {number} base
 * @param {number} exp
 * @returns {number}
 */
function power(base, exp) {
  if (typeof base !== 'number' || typeof exp !== 'number' || !Number.isFinite(base) || !Number.isFinite(exp)) {
    throw new TypeError('power: both arguments must be finite numbers');
  }
  return Math.pow(base, exp);
}

/**
 * Square root.
 * @param {number} x
 * @returns {number}
 */
function sqrt(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('sqrt: argument must be a finite number');
  }
  if (x < 0) {
    throw new RangeError('sqrt: argument must be non‑negative');
  }
  return Math.sqrt(x);
}

/**
 * Natural logarithm (ln).
 * @param {number} x
 * @returns {number}
 */
function ln(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('ln: argument must be a finite number');
  }
  if (x <= 0) {
    throw new RangeError('ln: argument must be positive');
  }
  return Math.log(x);
}

/**
 * Base‑10 logarithm.
 * @param {number} x
 * @returns {number}
 */
function log10(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('log10: argument must be a finite number');
  }
  if (x <= 0) {
    throw new RangeError('log10: argument must be positive');
  }
  // Use native Math.log10 when available, otherwise fallback.
  return Math.log10 ? Math.log10(x) : Math.log(x) / Math.LN10;
}

// Angle conversion helpers
const DEG_TO_RAD = Math.PI / 180;
const RAD_TO_DEG = 180 / Math.PI;

/**
 * Sine of an angle given in degrees.
 */
function sinDeg(angle) {
  if (typeof angle !== 'number' || !Number.isFinite(angle)) {
    throw new TypeError('sinDeg: angle must be a finite number');
  }
  return Math.sin(angle * DEG_TO_RAD);
}

/**
 * Cosine of an angle given in degrees.
 */
function cosDeg(angle) {
  if (typeof angle !== 'number' || !Number.isFinite(angle)) {
    throw new TypeError('cosDeg: angle must be a finite number');
  }
  return Math.cos(angle * DEG_TO_RAD);
}

/**
 * Tangent of an angle given in degrees.
 * Throws on angles where cosine is (practically) zero to avoid infinite results.
 */
function tanDeg(angle) {
  if (typeof angle !== 'number' || !Number.isFinite(angle)) {
    throw new TypeError('tanDeg: angle must be a finite number');
  }
  const rad = angle * DEG_TO_RAD;
  const cos = Math.cos(rad);
  if (Math.abs(cos) < Number.EPSILON) {
    throw new RangeError('tanDeg: angle results in division by zero (cosine ≈ 0)');
  }
  return Math.tan(rad);
}

/**
 * Arcsine returning degrees.
 */
function arcsinDeg(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('arcsinDeg: argument must be a finite number');
  }
  if (x < -1 || x > 1) {
    throw new RangeError('arcsinDeg: argument must be in [-1, 1]');
  }
  return Math.asin(x) * RAD_TO_DEG;
}

/**
 * Arccosine returning degrees.
 */
function arccosDeg(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('arccosDeg: argument must be a finite number');
  }
  if (x < -1 || x > 1) {
    throw new RangeError('arccosDeg: argument must be in [-1, 1]');
  }
  return Math.acos(x) * RAD_TO_DEG;
}

/**
 * Arctangent returning degrees.
 */
function arctanDeg(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) {
    throw new TypeError('arctanDeg: argument must be a finite number');
  }
  return Math.atan(x) * RAD_TO_DEG;
}

// Constants
const pi = Math.PI;
const e = Math.E;

// Export a single object containing everything.
export const MathHelpers = {
  factorial,
  power,
  sqrt,
  ln,
  log10,
  sinDeg,
  cosDeg,
  tanDeg,
  arcsinDeg,
  arccosDeg,
  arctanDeg,
  pi,
  e,
};

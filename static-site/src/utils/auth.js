import { Capacitor } from '@capacitor/core';
import { Preferences } from '@capacitor/preferences';

const isNative = Capacitor.isNativePlatform();
const USER_INFO_KEY = 'userInfo';

/**
 * Saves user information (id, username, password) to the appropriate storage.
 * @param {object} user - The user object to save.
 * @param {number} user.id - The user's ID.
 * @param {string} user.username - The user's username.
 * @param {string} user.password - The user's password.
 */
export const saveUser = async (user) => {
  if (!user || !user.id || !user.username || !user.password) {
      console.error("Attempted to save invalid user object", user);
      return;
  }
  const value = JSON.stringify(user);
  if (isNative) {
    await Preferences.set({ key: USER_INFO_KEY, value });
  } else {
    localStorage.setItem(USER_INFO_KEY, value);
  }
};

/**
 * Retrieves user information from storage.
 * @returns {Promise<object|null>} The user object or null if not found.
 */
export const getUser = async () => {
  if (isNative) {
    const result = await Preferences.get({ key: USER_INFO_KEY });
    return result.value ? JSON.parse(result.value) : null;
  } else {
    const value = localStorage.getItem(USER_INFO_KEY);
    try {
      return value ? JSON.parse(value) : null;
    } catch (e) {
      console.error("Failed to parse user info from localStorage", e);
      return null;
    }
  }
};

/**
 * Clears user information from storage.
 */
export const clearUser = async () => {
  if (isNative) {
    await Preferences.remove({ key: USER_INFO_KEY });
  } else {
    localStorage.removeItem(USER_INFO_KEY);
  }
}; 
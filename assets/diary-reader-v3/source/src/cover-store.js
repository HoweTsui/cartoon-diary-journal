const dbName = "diary-reader-v3-covers";
async function transact(bookId, action, value) {
  const db = await new Promise((resolve,reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore("covers");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  return new Promise((resolve,reject) => {
    const tx = db.transaction("covers", action === "get" ? "readonly" : "readwrite");
    const store = tx.objectStore("covers");
    const request = action === "put" ? store.put(value, bookId) : store[action](bookId);
    tx.oncomplete = () => { db.close(); resolve(request.result); };
    tx.onerror = tx.onabort = () => { db.close(); reject(tx.error || new Error("无法保存封面")); };
  });
}
export const readCover = id => transact(id, "get");
export const saveCover = (id,value) => transact(id, "put", value);
export const deleteCover = id => transact(id, "delete");

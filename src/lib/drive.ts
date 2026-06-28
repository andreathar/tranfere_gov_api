import { getAccessToken } from './auth';

export const saveToDrive = async (fileName: string, content: string) => {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");

  const metadata = {
    name: fileName,
    mimeType: 'application/json',
  };

  const file = new Blob([content], { type: 'application/json' });
  const form = new FormData();
  form.append('metadata', new Blob([JSON.stringify(metadata)], { type: 'application/json' }));
  form.append('file', file);

  const res = await fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: form,
  });
  if (!res.ok) {
    throw new Error('Failed to save to Drive');
  }
  return res.json();
};

export const loadFromDrive = async () => {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");

  // Get the most recent JSON file
  const res = await fetch('https://www.googleapis.com/drive/v3/files?q=mimeType="application/json"&orderBy=modifiedTime desc&pageSize=1', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to list files');
  const data = await res.json();
  if (!data.files || data.files.length === 0) return null;

  const fileId = data.files[0].id;
  
  // Download the content
  const dlRes = await fetch(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!dlRes.ok) throw new Error('Failed to download file');
  const content = await dlRes.text();
  return content;
};

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getToken } from '../../utils/auth';
import { motion } from 'framer-motion';
import Pagination from '../../components/ui/Pagination';
import { ArrowLeftIcon, XMarkIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { toast } from 'react-hot-toast';
import { apiUrl } from '../../utils/api';
import { ProtectedMedia, ProtectedAudio } from '../../components/ProtectedRoutes';

interface Upload {
  id: string;
  filename: string;
  title: string;
  description: string;
  created_at: string;
  audio_filename?: string;
  sentiment?: string;
}

const UserUploads = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const token = getToken();
  const [uploads, setUploads] = useState<Upload[]>([]);
  const userName = 'User';
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [currentAudio, setCurrentAudio] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);


  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pageSize, setPageSize] = useState(12);

  // Fetch uploads with pagination
  const fetchUploads = useCallback(async (page: number = 1, append: boolean = false) => {
    if (!userId) return;

    try {
      if (page === 1) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }


      const response = await fetch(apiUrl(`/api/admin/user_uploads/${userId}?page=${page}&page_size=${pageSize}`), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        credentials: 'include',
        mode: 'cors'
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log(data);
      if (data.error) {
        throw new Error(data.error);
      }
      
      const sortedImages: Upload[] = Array.isArray(data.images) ? data.images.sort((a: Upload, b: Upload) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()) : [];
      
      if (append) {
        setUploads(prev => [...prev, ...sortedImages]);
      } else {
        setUploads(sortedImages);
      }

      const normalizedTotalPages = typeof data.totalPages === 'number' ? data.totalPages : 0;
      setTotalPages(normalizedTotalPages > 0 ? normalizedTotalPages : 1);
      setTotalCount(data.total_count || 0);
      setCurrentPage(data.page || 1);
      
      console.log(`Loaded page ${page}/${normalizedTotalPages}, ${sortedImages.length} uploads`);

    } catch (error) {
      console.error('Error fetching uploads:', error);
      if (page === 1) {
        toast.error('Failed to fetch uploads');
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [userId, pageSize, token]);
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchUploads(page, false);
  };

  // Initial fetch
  useEffect(() => {
    if (userId) {
      setCurrentPage(1);
      fetchUploads(1, false);
    }
  }, [userId, fetchUploads]);

  // Pagination is handled via explicit controls (no infinite scroll)

  const handleFileClick = (filename: string) => {
    setSelectedFile(filename);
    setIsModalOpen(true);
  };

  const handleAudioClick = (audioFilename: string) => {
    if (currentAudio === audioFilename) {
      setCurrentAudio(null);
    } else {
      setCurrentAudio(audioFilename);
    }
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedFile(null);
  };

  const isPDF = (filename: string) => {
    return filename.toLowerCase().endsWith('.pdf');
  };

  const renderFilePreview = () => {
    if (!selectedFile) return null;
    const isPdfFile = isPDF(selectedFile);

    return (
      <ProtectedMedia
        filename={selectedFile}
        isPdf={isPdfFile}
        className={isPdfFile ? "w-full h-[80vh]" : "max-w-full h-auto mx-auto"}
      />
    );
  };

  const handleDownload = async (filename: string, type: 'file' | 'audio' = 'file') => {
    try {
      // Audio uses /api/audio/, images use /api/files/
      const endpoint = type === 'audio' ? '/api/audio/' + encodeURIComponent(filename) : '/api/files/' + encodeURIComponent(filename);

      const response = await fetch(apiUrl(endpoint), {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        credentials: 'include'
      });

      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename; // download instead of opening in tab
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success(`${type === 'file' ? 'File' : 'Audio'} downloaded successfully!`);
    } catch (error) {
      console.error('Download error:', error);
      toast.error('Failed to download file.');
    }
  };

  return (
    <div className="py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <motion.button
            onClick={() => navigate('/admin/users')}
            className="flex items-center text-gray-600 hover:text-yellow-500 transition-colors duration-200"
            whileHover={{ x: -4 }}
          >
            <ArrowLeftIcon className="h-5 w-5 mr-2" />
            Back to Users
          </motion.button>
          <h1 className="text-3xl font-bold mt-4">
            Uploads by {userName}
          </h1>
          <div className="mt-2 flex items-center space-x-4">
            {totalCount > 0 && (
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Showing {uploads.length} of {totalCount} uploads
              </p>
            )}
            <div className="flex items-center space-x-2">
              <label className="text-sm text-gray-600 dark:text-gray-300">Items:</label>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value) || 12);
                }}
                className="px-2 py-1 rounded-md bg-white dark:bg-gray-800 text-sm"
              >
                <option value={10}>10</option>
                <option value={12}>12</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex justify-center items-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-yellow-400"></div>
              </div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-yellow-200 dark:bg-gray-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Title
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Upload Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Sentiment
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Audio
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-black dark:text-gray-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {uploads.map((upload) => (
                    <motion.tr
                      key={upload.id}
                      className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-200"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => handleFileClick(upload.filename)}
                          className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          {upload.title}
                        </button>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {upload.description}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {new Date(upload.created_at).toLocaleString()}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {upload.sentiment || 'N/A'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {upload.audio_filename ? (
                          <div className="flex flex-col space-y-2">
                            <button
                              onClick={() => handleAudioClick(upload.audio_filename!)}
                              className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-200 ${currentAudio === upload.audio_filename
                                  ? 'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900 dark:text-red-100 dark:hover:bg-red-800'
                                  : 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-100 dark:hover:bg-blue-800'
                                }`}
                            >
                              {currentAudio === upload.audio_filename ? 'Hide Player' : 'Show Player'}
                            </button>
                            {currentAudio === upload.audio_filename && (
                              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 border border-gray-200 dark:border-gray-700">
                                <ProtectedAudio
                                  filename={upload.audio_filename}
                                  className="w-full [&::-webkit-media-controls-panel]:bg-gray-100 dark:[&::-webkit-media-controls-panel]:bg-gray-800 [&::-webkit-media-controls-current-time-display]:text-gray-700 dark:[&::-webkit-media-controls-current-time-display]:text-gray-300 [&::-webkit-media-controls-time-remaining-display]:text-gray-700 dark:[&::-webkit-media-controls-time-remaining-display]:text-gray-300 [&::-webkit-media-controls-timeline]:bg-gray-300 dark:[&::-webkit-media-controls-timeline]:bg-gray-600 [&::-webkit-media-controls-volume-slider]:bg-gray-300 dark:[&::-webkit-media-controls-volume-slider]:bg-gray-600"
                                  onEnded={() => setCurrentAudio(null)}
                                />
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            N/A
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center space-x-3">
                          <button
                            onClick={() => handleDownload(upload.filename, 'file')}
                            className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-yellow-100 text-yellow-700 hover:bg-yellow-200 dark:bg-yellow-900 dark:text-yellow-100 dark:hover:bg-yellow-800 transition-colors duration-200"
                            title="Download File"
                          >
                            <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                            File
                          </button>
                          {upload.audio_filename && (
                            <button
                              onClick={() => handleDownload(upload.audio_filename!, 'audio')}
                              className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-100 dark:hover:bg-blue-800 transition-colors duration-200"
                              title="Download Audio"
                            >
                              <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                              Audio
                            </button>
                          )}
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="p-4">
            <Pagination page={currentPage} totalPages={totalPages} onPageChange={handlePageChange} />
          </div>



          {/* Loading indicator */}
          {loadingMore && (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-yellow-400"></div>
            </div>
          )}

          {/* End of page indicator */}
          {currentPage >= totalPages && uploads.length > 0 && (
            <div className="flex justify-center py-8">
              <p className="text-gray-500 dark:text-gray-400 text-center">
                You've viewed all {totalCount} uploads
              </p>
            </div>
          )}
        </div>
      </div>

      {/* File Preview Modal */}
      {isModalOpen && selectedFile && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" aria-hidden="true">
              <div className="absolute inset-0 bg-gray-500 dark:bg-gray-900 opacity-75"></div>
            </div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full">
              <div className="absolute top-0 right-0 pt-4 pr-4">
                <button
                  onClick={closeModal}
                  className="bg-white dark:bg-gray-800 rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
                >
                  <span className="sr-only">Close</span>
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>
              <div className="px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="mt-3 text-center sm:mt-0 sm:text-left">
                  <div className="mt-2">
                    {renderFilePreview()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserUploads; 
// Created by Metrum AI for Solidigm

import { useState, useEffect } from 'react';
import { Book, RefreshCw, Check, Loader2 } from 'lucide-react';
import styles from '@/styles/components/BookSelector.module.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

interface BookInfo {
  id: string;
  name: string;
  filename: string;
  word_count: number;
  size_bytes: number;
}

interface BookSelectorProps {
  onBookSelect: (content: string, bookName: string) => void;
  selectedBook: string | null;
}

export function BookSelector({ onBookSelect, selectedBook }: BookSelectorProps) {
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingBook, setLoadingBook] = useState<string | null>(null);

  const fetchBooks = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/context/books`);
      if (response.ok) {
        const data = await response.json();
        setBooks(data.books || []);
      }
    } catch (error) {
      console.error('Failed to fetch books:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBooks();
  }, []);

  const handleBookClick = async (book: BookInfo) => {
    setLoadingBook(book.id);
    try {
      const response = await fetch(`${API_BASE}/api/v1/context/books/${book.id}?max_chars=400000`);
      if (response.ok) {
        const data = await response.json();
        onBookSelect(data.content, data.name);
      }
    } catch (error) {
      console.error('Failed to load book:', error);
    } finally {
      setLoadingBook(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIcon}>
            <Book className={styles.headerIconInner} />
          </div>
          <h3 className={styles.title}>Sample Books</h3>
          <span className={styles.badge}>{books.length}</span>
        </div>
        <button
          onClick={fetchBooks}
          disabled={loading}
          className={styles.refreshButton}
        >
          <RefreshCw className={`${styles.refreshIcon} ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <p className={styles.description}>
        Click a book to load as context (~100K tokens each)
      </p>

      <div className={styles.list}>
        {books.length === 0 && !loading ? (
          <div className={styles.emptyState}>
            <Book className={styles.emptyIcon} />
            <p className={styles.emptyText}>No books available</p>
          </div>
        ) : (
          books.map((book) => {
            const isSelected = selectedBook === book.id;
            const isLoading = loadingBook === book.id;

            return (
              <button
                key={book.id}
                onClick={() => handleBookClick(book)}
                disabled={loadingBook !== null}
                className={`${styles.bookItem} ${isSelected ? styles.bookItemSelected : ''}`}
              >
                <div className={styles.bookInfo}>
                  {isLoading ? (
                    <Loader2 className={`${styles.loadingIcon} animate-spin`} />
                  ) : (
                    <Book className={styles.bookIcon} />
                  )}
                  <div className={styles.bookDetails}>
                    <p className={styles.bookName}>{book.name}</p>
                    <p className={styles.bookStats}>
                      {book.word_count.toLocaleString()} words • {formatSize(book.size_bytes)}
                    </p>
                  </div>
                </div>
                {isSelected && <Check className={styles.checkIcon} />}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

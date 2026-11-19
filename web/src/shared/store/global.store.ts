import { create } from "zustand";

interface SearchState {
  query: string;
  isOpen: boolean;
  setQuery: (query: string) => void;
  setIsOpen: (isOpen: boolean) => void;
}

export const useSearch = create<SearchState>((set) => ({
  query: "",
  isOpen: false,
  setQuery: (query) => set({ query }),
  setIsOpen: (isOpen) => set({ isOpen }),
}));

interface SidebarState {
  isOpen: boolean;
  toggleOpen: () => void;
  setOpen: (isOpen: boolean) => void;
}

export const useSidebar = create<SidebarState>((set) => ({
  isOpen: true,
  toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
  setOpen: (isOpen) => set({ isOpen }),
}));

interface DocumentationState {
  currentPath: string;
  setCurrentPath: (path: string) => void;
  tableOfContents: Array<{ id: string; label: string; level: number }>;
  setTableOfContents: (
    toc: Array<{ id: string; label: string; level: number }>,
  ) => void;
}

export const useDocumentation = create<DocumentationState>((set) => ({
  currentPath: "/docs/introduction",
  setCurrentPath: (path) => set({ currentPath: path }),
  tableOfContents: [],
  setTableOfContents: (toc) => set({ tableOfContents: toc }),
}));

export const useGlobal = () => {
  //set mode
  onMounted(() => {
    useDarkMode()
      ? document.querySelector("html")?.classList.add("dark")
      : document.querySelector("html")?.classList.remove("dark");
  });
};

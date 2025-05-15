/* 
Javascript functions to help make the print page more PDF friendly
*/

/*
Copy the table of contents from the sidebar's.
Only called when print-site-plugin option 'add_table_of_contents' is set to true
*/
function generate_toc() {
  const sidebar = document.body.getElementsByClassName("md-sidebar--secondary")[0] ??
    document.getElementById("toc-collapse");

  const sidebarToc = sidebar.getElementsByTagName("ul")[0];

  var clonedToc = sidebarToc.cloneNode(true);
  clonedToc.removeAttribute("data-md-component");
  document.querySelectorAll("#print-page-toc nav")[0].insertAdjacentHTML("beforeend", clonedToc.outerHTML);
}


function remove_material_navigation() {
  // Remove left sidebar on print page
  remove_element_by_classname("md-sidebar--primary")
  // Remove tabs navigation on print page
  remove_element_by_classname("md-tabs")
  // Remove search
  remove_element_by_classname("md-search")

}

function remove_mkdocs_theme_navigation() {
  // Remove top navigation bar
  remove_element_by_classname("navbar")
}


function remove_element_by_classname(class_name) {
  var el = document.getElementsByClassName(class_name);
  if( el.length > 0) {
    el[0].style.display = "none"
  }
}

/* 
Javascript functions to help make the print page more PDF friendly
*/

/*
Generates a table of contents for the print site page.
Only called when print-site-plugin option 'add_table_of_contents' is set to true
*/
function generate_toc() {

  var ToC = ""

  var newLine, el, title, link;

  const toc_elements = document.querySelectorAll(
    "#print-site-page h1.nav-section-title, #print-site-page h1.nav-section-title-end," +
    "#print-site-page h2.nav-section-title, #print-site-page h2.nav-section-title-end," +
    "#print-site-page h3.nav-section-title, #print-site-page h3.nav-section-title-end," +
    "#print-site-page h4.nav-section-title, #print-site-page h4.nav-section-title-end," +
    "#print-site-page h5.nav-section-title, #print-site-page h5.nav-section-title-end," +
    "#print-site-page h6.nav-section-title, #print-site-page h6.nav-section-title-end," +
    "section.print-page h1,section.print-page h2,section.print-page h3," +
    "section.print-page h4,section.print-page h5,section.print-page h6")
  
  var current_heading_depth = 0;
  var current_section_depth = 0;

  // Extract table of contents depth
  // basically plugin setting, passed via a data attribute
  var toc_depth = document.getElementById("print-page-toc").getAttribute("data-toc-depth")

  for (var i = 0; i < toc_elements.length; i++) {
    
    // Get the info from the element
    el = toc_elements[i]
    link = "#" + el.id;
    tag = el.tagName
    tag_level = tag.substring(1)
    // Get the text of a heading
    // We use .firstChild.nodeValue instead of .innerText
    // because of elements like:
    // <h1 id="index-mkdocs-print-site-plugin">
    //     mkdocs-print-site-plugin<a class="headerlink" href="#index-mkdocs-print-site-plugin" title="Permanent link">↵</a>
    //  </h1>
    title = el.firstChild.nodeValue;
    if ( ! title ) {
      continue;
    }

    // Don't put the toc h1 in the toc
    if ( el.classList.contains('print-page-toc-title') ) {
      continue;
    }
    // Ignore the MkDocs keyboard Model
    if ( el.id.indexOf("keyboardModalLabel") > -1 ) {
      continue;
    }

    // print-site-plugin has a setting to control TOC depth
    if ( tag_level > toc_depth ) {
      continue;
    }

    if (el.classList.contains('nav-section-title') ) {
      // Use the tag level of the first item in the section to close off any nested <ul>
      el = toc_elements[i+1]
      link = "#" + el.id;
      tag = el.tagName
      tag_level = tag.substring(1)
      while (tag_level > current_heading_depth) {
        current_heading_depth++;
        ToC += "<ul class='print-site-toc-level-" + current_heading_depth + "'>";
      }
      while (tag_level < current_heading_depth) {
        current_heading_depth--;
        ToC += "</ul>"; 
      }

      // Insert a section heading <li> item, however deeply we are nested.
      current_section_depth++;
      // Insert item as a section title in the current list
      ToC += "<li class='toc-nav-section-title toc-nav-section-title-level-" + (current_section_depth) + "'>" + title + "</li>";
      
      // Start a new ul for the section
      ToC += "<ul class='print-site-toc-level-" + current_heading_depth + " toc-section-line-border'>";
      continue;
    }


    if (el.classList.contains('nav-section-title-end') ) {

      current_section_depth--;
      // Close the special section ul
      ToC += "</ul>";

      continue;
    }

    while (tag_level > current_heading_depth) {
      current_heading_depth++;
      ToC += "<ul class='print-site-toc-level-" + current_heading_depth + "'>";
    }
    while (tag_level < current_heading_depth) {
      current_heading_depth--;
      ToC += "</ul>"; 
    }


    newLine = "<li>" +
      "<a href='" + link + "'>" +
        title +
      "</a>" +
    "</li>";

    ToC += newLine;

  };

  ToC += "</ul>"

  document.querySelectorAll("#print-page-toc nav")[0].insertAdjacentHTML("beforeend", ToC);

}


function remove_material_navigation() {

  // Remove left sidebar on print page
  remove_element_by_classname('md-sidebar--primary')
  // Remove tabs navigation on print page
  remove_element_by_classname('md-tabs')
  // Remove search
  remove_element_by_classname('md-search')

}

function remove_mkdocs_theme_navigation() {

  // Remove top navigation bar
  remove_element_by_classname('navbar')
}


function remove_element_by_classname(class_name) {
  var el = document.getElementsByClassName(class_name);
  if( el.length > 0) {
    el[0].style.display = "none"
  }
}

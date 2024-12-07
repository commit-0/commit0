document$.subscribe(function() {
  var tables = document.querySelectorAll("article table:not([class])")
  tables.forEach(function(table) {
    new Tablesort(table);
    // Automatically sort the table by the specified column
    var defaultSortColumn = 2; // Index of the column to sort (0-based)
    var isAscending = False;   // Set to false for descending order

    // Delay to ensure Tablesort is fully initialized
    setTimeout(function () {
      var header = table.querySelectorAll("thead th")[defaultSortColumn];
      if (header) {
        header.click(); // Simulate a click on the header
        if (!isAscending) {
          header.click(); // Click again for descending order
        }
      }
    }, 100);
  });
});
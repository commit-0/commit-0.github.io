document$.subscribe(function () {
  var tables = document.querySelectorAll("article table:not([class])");

  tables.forEach(function (table) {
    // Initialize Tablesort
    var tablesortInstance = new Tablesort(table);

    // Extend Tablesort for numeric sorting
    Tablesort.extend('number', function (item) {
      return !isNaN(item); // Check if the item is numeric
    }, function (a, b) {
      return parseFloat(a) - parseFloat(b); // Compare numbers
    });

    // Automatically sort the table by the specified column
    var defaultSortColumn = 2; // Index of the column to sort (0-based)
    var isAscending = true;   // Set to false for descending order

    // Delay to ensure Tablesort is fully initialized before sorting
    setTimeout(function () {
      var header = table.querySelectorAll("thead th")[defaultSortColumn];
      if (header) {
        header.click(); // Simulate a click on the header
        if (!isAscending) {
          header.click(); // Click again if descending order is needed
        }
      }
    }, 100);
  });
});

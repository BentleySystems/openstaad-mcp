// take-screenshot.js
// Takes an isometric screenshot of the current model.

const view = staad.View;

view.ShowIsometric();
view.ZoomExtentsMainView();

// Show node and beam numbers
view.SetLabel(0, true);   // node numbers
view.SetLabel(1, true);   // beam numbers

view.RefreshView();

// Export to file
// IMPORTANT: Ask the user where to save the screenshot.
// Do NOT hardcode a path — use the directory the user provides.
const status = view.ExportView('C:\\Users\\<username>\\Documents', 'model_screenshot', 1, true);
console.log(`Screenshot status: ${status}`);  // 1 = success

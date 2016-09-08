(function ($) {
  $(document).ready(function(){

  // get distance from top of the bottom logo border
  logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top

  // user can load already scrolled page (eg. refreshing, ...); check it even on document ready
  if ($(this).scrollTop() > logo_pos) {
    $('.navbar-brand').fadeIn();
  } else {
    $('.navbar-brand').fadeOut();
  }

  // hook on scroll and show/hide navbar
  $(function () {
    $(window).scroll(function () {
      // set distance user needs to scroll before we fadeIn navbar
      // FIXME: Make this START at the ABOUT page
      if ($(this).scrollTop() > logo_pos) {
        $('.navbar-brand').fadeIn();
      } else {
        $('.navbar-brand').fadeOut();
      }
    });


  });

});
  }(jQuery));

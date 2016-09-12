function scroll_to_section(section /* Pass element id with # */) {
  // Get position of scroll target from top
  scroll_to = $(section).offset().top - $("#page-top").offset().top - ( $(section + " h2").outerHeight() / 2 )
  $('html, body').animate({
    scrollTop: scroll_to
 }, 1000);
}

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
      // Keep amount of things here at minimum to keep it smooth on low-end devices
      if ($(this).scrollTop() > logo_pos) {
        $('.navbar-brand').fadeIn();
      } else {
        $('.navbar-brand').fadeOut();
      }
    });


  });

});
  }(jQuery));
